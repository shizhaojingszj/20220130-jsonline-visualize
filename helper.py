import json
import pdb
import re
import sys
import textwrap
from functools import wraps
from pathlib import Path
from typing import IO, Dict, Iterator, List, Tuple, Union, Any
from xmlrpc.client import Boolean

import click
import glom  # type: ignore
import numpy as np
import pandas as pd
import seaborn as sns  # type: ignore
from matplotlib import pyplot as plt  # type: ignore
from typing_extensions import TypeAlias


# helper
def should_ignore(temp: str) -> bool:
    return temp.startswith("#") or not temp


ValueInDataFrame: TypeAlias = Union[float, str]


def parsed_any_info(func):
    @wraps(func)
    def inner(self, *args, **kwargs):
        if "any_info" in kwargs:
            any_info = kwargs.pop("any_info")
            if hasattr(self, "parse_any_info"):
                parse_any_info_func = getattr(self, "parse_any_info")
                thing = parse_any_info_func(any_info)
                kwargs.update(thing)
        return func(self, *args, **kwargs)

    return inner


class ConfusionMatrix:
    def __init__(self, indir: str, outfile: str):
        self.indir = indir
        self.outfile = outfile

    def calculate_acc(self, df: pd.DataFrame) -> Dict[str, ValueInDataFrame]:
        labels = df.columns
        res: dict = {}
        assert df.shape[0] == df.shape[1], df.head()
        res["acc"] = 0
        for index, label in enumerate(labels):
            res[f"{label}_acc"] = df.loc[index, label] / np.sum(df[label])
            res["acc"] += df.loc[index, label]
        res["acc"] = res["acc"] / np.sum(np.sum(df))
        return res

    def convert(
        self, infile_list: Dict[int, str], info: str
    ) -> List[Dict[str, ValueInDataFrame]]:
        res: List[Dict[str, ValueInDataFrame]] = []
        for epoch_step, csv_file in infile_list.items():
            df1 = pd.read_csv(csv_file)
            acc_dict1 = self.calculate_acc(df1)
            acc_dict1["epoch"] = epoch_step
            acc_dict1["type"] = info
            res.append(acc_dict1)
        return res

    def find_csv_files(self, indir: str, prefix="train_epoch") -> Dict[int, str]:
        """
        e.g. /mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp/config.5.20220207_175258.json/ckpt/inceptionv3_class3_0207/tile299/confuse_matrix
        """
        pat = re.compile(f"^{prefix}(?P<idx>\d+)\.csv$")
        res: Dict[int, str] = {}
        for csv_file in Path(indir).glob("*.csv"):
            match = pat.match(csv_file.name)
            if not match:
                continue
            idx = int(match.groupdict()["idx"])
            res[idx] = str(csv_file.absolute())
        return res

    def parse_any_info(self, any_info: List[str]) -> Dict[str, str]:
        res = {}
        for info in any_info:
            k, v = glom.glom(info, lambda x: x.split("=", 1))
            res[k] = v
        return res

    def run(self, any_info: List[str]):
        train_files = self.find_csv_files(self.indir, prefix="train_epoch")
        val_files = self.find_csv_files(self.indir, prefix="val_epoch")
        # to jsonline
        with open(self.outfile, "w") as OUT:  # write both train and val to one file
            # train
            train_info = self.convert(train_files, "train")
            for train_epoch_info in train_info:
                print(json.dumps(train_epoch_info), file=OUT)
            print(f"{len(train_info)} training epoches output to {self.outfile}")
            # val
            val_info = self.convert(val_files, "val")
            for val_epoch_info in val_info:
                more = {
                    **val_epoch_info,
                    **self.parse_any_info(any_info),
                }
                print(json.dumps(more), file=OUT)
            print(f"{len(val_info)} validation output to {self.outfile}")


class Plot:
    def __init__(self, infile: str, outfile: str):
        self.infile = infile
        self.outfile = outfile

    def setup_seaborn(self, **kwargs):
        if "context" in kwargs:
            sns.set_context(glom.glom(kwargs, "context"))
        if "palette" in kwargs:
            sns.set_palette(glom.glom(kwargs, "palette"))
        if "figsize" in kwargs:
            sns.set(rc={"figure.figsize": glom.glom(kwargs, "figsize")})

    def run(
        self,
        *,
        context: str = "talk",
        palette: str = "blue",
        x: str = "wholestep,epoch",
        y: List[str] = ["valid", "train", "lr"],
        figsize=(12, 8),
    ):

        self.setup_seaborn(
            context=context,
            palette=palette,
            figsize=figsize,
        )

        # 1. filter data with y
        good_data = JsonlineReader(self.infile).only_data_with_y(y)

        # 2. plot one by one
        if not good_data:
            print("No y is available in the infile: %s" % self.infile)
            return 1

        xs: List[str] = x.split(",")
        print(f"xs is {xs}")

        subplots_number = len(good_data)
        fig, axs = plt.subplots(nrows=subplots_number, squeeze=True)
        for n, (some_y, some_data) in enumerate(good_data):
            data_df = pd.DataFrame.from_records(some_data)
            x1 = [x0 for x0 in xs if x0 in data_df.columns]
            print(f"x1 is {x1}")
            if x1:
                # only first x is used
                if subplots_number == 1:
                    ax = axs
                else:
                    ax = axs[n]
                sns.lineplot(x=x1[0], y=some_y, data=data_df, ax=ax)
        fig.savefig(self.outfile, bbox_inches="tight")


class CombinedPlotter(Plot):
    """
    ??????plotter?????????????????????????????????????????????????????? + ????????????json????????????\t??????
    e.g. /mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp/config.10.20220208_220626.json/ckpt/inceptionv3_class3_0208/tile299/confuse_matrix/
        \t
        /mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp/json_output/config.10.20220208_220626.json
    """

    def parse_input(self) -> List[Tuple[str, str]]:
        res = []
        with open(self.infile) as IN:
            for line in IN:
                temp = line.strip()
                if should_ignore(temp):
                    continue
                folder: str  # confusion_matrix_output_folder
                json_file: str  # json file with information
                folder, json_file = glom.glom(temp, lambda x: x.split("\t"))
                res.append((folder, json_file))
        return res


class Plot2(Plot):
    """
    ?????????line????????????
    """

    def get_title_info(self, title_info: Dict, **kwargs) -> str:
        info: List[str] = textwrap.wrap(json.dumps(title_info), **kwargs)
        return "\n" + "\n".join(info)

    def parse_any_info(self, any_info: str):
        with open(any_info) as IN:
            parsed_info = json.load(IN)
        title = "Acc"
        title_info = parsed_info
        return {
            "title": title,
            "title_info": title_info,
        }

    @parsed_any_info
    def run(
        self,
        *,
        context: str = "talk",
        palette: str = "blue",
        x: str = "wholestep,epoch",
        y: List[str] = ["acc", "normal_acc", "luad_acc", "lusc_acc"],
        figsize=(12, 8),
        title_info: Dict = {},  # ?????????????????????????????????????????????????????????title??????
        title: str = "Acc",
    ):
        self.setup_seaborn(
            context=context,
            palette=palette,
            figsize=figsize,
        )

        xs: List[str] = x.split(",")
        print(f"xs is {xs}")

        # 1. ????????????????????????????????????y???????????????y???????????????
        y0 = y[0]
        good_data = JsonlineReader(self.infile).only_data_with_y([y0])

        # ???????????????????????????
        for n, (some_y, some_data) in enumerate(good_data):
            assert n == 0
            x1 = [x0 for x0 in xs if x0 in glom.glom(some_data, glom.T[0])]
            print(f"x1 is {x1}")
            xlabel = None
            if x1:
                ### ???????????????x???????????????????????? ###
                # only first x is used
                xlabel = x1[0]
            if not xlabel:
                raise ValueError(f"No x({xs}) is found in file({self.infile})")
            select_columns = ["type", xlabel] + y
            data_df = pd.DataFrame.from_records(some_data, columns=select_columns)
            # melt
            df2 = pd.melt(data_df, [xlabel, "type"])
            sns_plot = sns.lineplot(
                x=xlabel,
                y="value",
                hue="variable",
                data=df2,
                style="type",
                palette=palette,
            )
            if title_info:
                title1 = title + self.get_title_info(title_info)
            else:
                title1 = title
            sns_plot.set_title(title1)
            fig = sns_plot.get_figure()
            if self.outfile:
                fig.savefig(self.outfile, bbox_inches="tight")
            else:
                return {
                    "data": df2,
                    "plot": sns_plot,
                }


class JsonlineReader:
    def __init__(self, infile: str):
        self.infile = infile

    def filter_data_with_y(self, y: str) -> Iterator[Dict]:
        with open(self.infile) as IN:
            for line in IN:
                temp = line.strip()
                if should_ignore(temp):
                    continue
                parsed: Dict = json.loads(temp)
                if y in parsed:
                    yield parsed

    def only_data_with_y(self, y: List[str]):
        # now finish this
        # 1. parse data
        good_data: List[Tuple[str, List[Dict]]] = []
        for some_y in y:
            some_data = list(self.filter_data_with_y(some_y))
            if some_data:
                good_data.append((some_y, some_data))
        return good_data


class CombinedPlotter1(CombinedPlotter):
    def get_title_info(self, title_info: Dict, **kwargs) -> str:
        info: List[str] = textwrap.wrap(json.dumps(title_info), **kwargs)
        return "\n" + "\n".join(info)

    def parse_any_info(self, any_info: str) -> Dict[str, Any]:
        """
        any_info: subset_json_list
        ??????????????????????????????field???\\t??????
        ?????????<config_json_base_name>\t<subset_json_fullpath>\t<jsonline_fullpath>
        """
        pat = re.compile("(?P<base>.*)\.subset\.json")
        # def get_json_basename(filename: str):
        #     spec = (lambda x: pat.match(x), glom.T.groupdict(), "base")
        #     return glom.glom(Path(filename).name, spec)
        all_lines = []
        with open(any_info) as IN:
            for line in IN:
                temp = line.strip()
                if should_ignore(temp):
                    continue
                fields = glom.glom(temp, (glom.T.split("\t"),))
                assert len(fields) == 3, fields
                all_lines.append(fields)
        # ???subset_json????????????????????????????????????????????????????????????????????????
        # ?????????key???config_json_basename
        subset_json_info: Dict[str, Dict] = {}
        jsonline_info: Dict[str, str] = {}
        for config_json_base_name, subset_json_fullpath, jsonline_fullpath in all_lines:
            with open(subset_json_fullpath) as IN:
                subset_info = json.load(IN)
            subset_json_info[config_json_base_name] = subset_info
            jsonline_info[config_json_base_name] = jsonline_fullpath
        title = "Acc"
        title_info = subset_json_info
        # ???????????????????????????run???????????????
        return {
            "title": title,
            "title_info": title_info,
            "jsonline_info": jsonline_info,
        }

    @parsed_any_info
    def run(
        self,
        *,
        context: str = "talk",
        palette: str = "Blues",
        x: str = "epoch",
        y: List[str] = ["acc", "normal_acc", "luad_acc", "lusc_acc"],
        title: str,
        title_info: Dict[str, Dict],
        jsonline_info: Dict[str, str],
        figsize=(30, 24),
        plot_grid=(2, 4),
        xlimits=None,
        ylimits=None,
        title_wrap_width=70,
        # jsonnet config sns
    ):

        # ?????????????????????????????????????????????????????????debug??????
        folder_info = self.parse_input()

        # ??????????????????plot_grid?????????????????????
        assert len(folder_info) <= plot_grid[0] * plot_grid[1], (
            folder_info,
            plot_grid,
        )

        self.setup_seaborn(
            context=context,
            palette=palette,
            figsize=figsize,
        )

        xs: List[str] = x.split(",")
        print(f"xs is {xs}")

        def to_df(config_json_base_name: str, jsonline_file: str) -> pd.DataFrame:
            y0 = y[0]
            good_data = JsonlineReader(jsonline_file).only_data_with_y([y0])
            for n, (some_y, some_data) in enumerate(good_data):
                assert n == 0
                x1 = [x0 for x0 in xs if x0 in glom.glom(some_data, glom.T[0])]
                print(f"x1 is {x1}")
                xlabel = None
                if x1:
                    ### ???????????????x???????????????????????? ###
                    # only first x is used
                    xlabel = x1[0]
                if not xlabel:
                    raise ValueError(f"No x({xs}) is found in file({self.infile})")
                select_columns = ["type", xlabel] + y
                data_df = pd.DataFrame.from_records(some_data, columns=select_columns)
                # melt
                df2 = pd.melt(data_df, [xlabel, "type"])
                df2["name"] = config_json_base_name
                return df2
            raise NotImplementedError("cannot get here")

        jsonline_to_df = glom.glom(
            jsonline_info.items(),
            ([lambda item: to_df(item[0], item[1])],),
        )

        combined_df = pd.concat(jsonline_to_df)
        combined_df.to_csv(self.outfile + ".df")

        # real plot
        fig, axes = plt.subplots(nrows=plot_grid[0], ncols=plot_grid[1], squeeze=True)
        axes = axes.flatten()
        for n, name in enumerate(sorted(combined_df.name.unique())):
            sub_df = combined_df[combined_df.name == name]
            sns_plot = sns.lineplot(
                x="epoch",
                y="value",
                hue="variable",
                data=sub_df,
                style="type",
                palette="husl",
                ax=axes[n],
            )
            title_info1 = title_info[name]
            if title_info1:
                title1 = title + self.get_title_info(title_info1, width=title_wrap_width)
            sns_plot.set_title(title1)
            if xlimits:
                sns_plot.set_xlim(xlimits[0], xlimits[1])
            if ylimits:
                sns_plot.set_ylim(ylimits[0], ylimits[1])
        fig.savefig(self.outfile)


class TemporaryConverter:
    def __init__(self, infile: str, outfile: str):
        self.infile = infile
        self.outfile = outfile

    def convert_old_formats(self, obj: Dict) -> Dict:
        # log_9.txt => {"epoch1": {"step0": {"train": 1.7113, "lr": 0.01}}}
        # log_100.txt => {"epoch2": {"valid": 1.0219}}
        # log.txt => 1. {"epoch292": {"step1715": {}, "valid": 0.8156}}
        #            2. {"epoch0": {"step0": {"train": 1.2284, "lr": 0.01}}}
        pat = re.compile("(\D+)(\d+)")

        def get_number_from_key(d: Dict) -> List[Tuple[str, int]]:
            """Just a flatten function

            Args:
                d (Dict): [description]

            Returns:
                List[Tuple[str, int]]: [description]
            """
            res = []
            for key, value in d.items():
                m = pat.match(key)
                if m:
                    column, value2 = m.groups()
                    res.append((column, int(value2)))
                if isinstance(value, dict):
                    # only recursive here
                    res.extend(get_number_from_key(value))
                if not m:
                    res.append((key, value))
            return res

        res = dict(get_number_from_key(obj))
        return res

    def run(self):
        """??????????????????????????????????????????????????????????????????pandas???????????????jsonline??????"""
        with open(self.infile) as IN, open(self.outfile, "w") as OUT:
            for line in IN:
                temp = line.strip()
                if temp.startswith("#") or not temp:
                    continue
                # jsonline
                parsed = json.loads(temp)
                new_format = self.convert_old_formats(parsed)
                print(json.dumps(new_format), file=OUT)


class Transformer:
    def __init__(self, infile: str, outfile: str):
        self.infile = infile
        self.outfile = outfile

    def rescue(self, obj: Dict, max_step: int = -1) -> Dict:
        # rescue step with epoch
        if "step" in obj and "epoch" in obj and max_step > 0:
            obj["wholestep"] = glom.glom(obj, "epoch") * max_step + glom.glom(
                obj, "step"
            )
        return obj

    def run(self):
        """??????????????????????????????????????????????????????????????????pandas???????????????jsonline??????"""
        max_step = -1

        # 1st iteration, calculate max_step
        with open(self.infile) as IN:
            for line in IN:
                temp = line.strip()
                if should_ignore(temp):
                    continue
                parsed = json.loads(temp)
                if "step" in parsed:
                    max_step = max(parsed["step"], max_step)

        # 2nd iteration
        with open(self.infile) as IN, open(self.outfile, "w") as OUT:
            for line in IN:
                temp = line.strip()
                if should_ignore(temp):
                    continue
                # jsonline
                parsed = json.loads(temp)
                new_format = self.rescue(parsed, max_step)
                print(json.dumps(new_format), file=OUT)


class SubsetJson:
    def __init__(self, infile: str, outfile: str):
        self.infile = infile
        self.outfile = outfile

    def run(self, specs: List[str]) -> None:
        with open(self.infile) as IN:
            parse_input = json.load(IN)
        res = {}
        for spec in specs:
            res[spec] = glom.glom(parse_input, spec)
        with open(self.outfile, "w") as OUT:
            print(json.dumps(res), file=OUT)


@click.group()
def cli():
    pass


@cli.command("normalize-old-formats")
@click.option("-i", "--infile", required=True)
@click.option("-o", "--outfile", required=True)
def parse_xlsx(infile, outfile):
    TemporaryConverter(infile, outfile).run()


@cli.command("rescue-normalized-file")
@click.option("-i", "--infile", required=True)
@click.option("-o", "--outfile", required=True)
def rescue(infile, outfile):
    Transformer(infile, outfile).run()


@cli.command("plot-jsonline")
@click.option("-i", "--infile", required=True)
@click.option("-o", "--outfile", required=True)
@click.option("--sns-context", default="talk")
@click.option("--sns-palette", default="Reds")
@click.option("-x", default="wholestep,epoch")
@click.option("--ys", default="valid,train,lr")
@click.option("--class-name", default="Plot")
@click.option("--fig-size", default="12,8")
@click.argument("any_info", type=str, default="")
def generate_shell(
    infile,
    outfile,
    sns_context,
    sns_palette,
    x,
    ys,
    class_name,
    any_info,
    fig_size,
):
    Plot_class = globals()[class_name]
    kwargs = {}
    if any_info:
        kwargs = {"any_info": any_info}
    Plot_class(infile, outfile).run(
        context=sns_context,
        palette=sns_palette,
        x=x,
        y=ys.split(","),
        figsize=fig_size.split(","),
        **kwargs,
    )


@cli.command("plot-jsonline2", help="use jsonnet")
@click.option("--config-json", required=True)
@click.argument("any_info", type=str, default="")
def generate_shell(any_info, config_json):
    with open(config_json) as IN:
        json_config = json.load(IN)

    def j(spec):
        return glom.glom(json_config, spec)

    Plot_class = globals()[j("class_name")]
    kwargs = {}
    if any_info:
        kwargs = {"any_info": any_info}
    Plot_class(j("infile"), j("outfile")).run(
        **j("sns"),
        **kwargs,
    )


@cli.command("from-confusion-matrix-to-jsonline")
@click.option("-i", "--infile", required=True)
@click.option("-o", "--outfile", required=True)
@click.argument("any_info", type=str, nargs=-1)
def from_confusion_matrix_to_jsonline(infile, outfile, any_info):
    ConfusionMatrix(infile, outfile).run(any_info)


@cli.command("subset-json")
@click.option("-i", "--infile", required=True)
@click.option("-o", "--outfile", required=True)
@click.argument("specs", type=str, nargs=-1)
def subset_json(infile, outfile, specs):
    SubsetJson(infile, outfile).run(specs)


if __name__ == "__main__":
    cli()

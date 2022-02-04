import json
import pdb
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Iterator

import click
import glom  # type: ignore
import pandas as pd

import seaborn as sns # type: ignore
from matplotlib import pyplot as plt # type: ignore


# helper
def should_ignore(temp: str) -> bool:
    return temp.startswith("#") or not temp


class Plot:
    def __init__(self, infile: str, outfile: str):
        self.infile = infile
        self.outfile = outfile

    def filter_data_with_y(self, y: str) -> Iterator[Dict]:
        with open(self.infile) as IN:
            for line in IN:
                temp = line.strip()
                if should_ignore(temp):
                    continue
                parsed: Dict = json.loads(temp)
                if y in parsed:
                    yield parsed

    def run(
        self,
        *,
        context: str = "talk",
        palette: str = "blue",
        x: str = "wholestep,epoch",
        y: List[str] = ["valid", "train", "lr"],
    ):

        sns.set_context(context)
        sns.set_palette(palette)
        sns.set(rc={'figure.figsize':(12, 8)})

        # now finish this
        # 1. parse data
        good_data: List[Tuple[str, List[Dict]]] = []
        for some_y in y:
            some_data = list(self.filter_data_with_y(some_y))
            if some_data:
                good_data.append((some_y, some_data))
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
        fig.savefig(self.outfile, bbox_inches='tight')


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
        """就是将几种模式的“不标准”，变成后续能够读入pandas的“简单”jsonline格式
        """
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
        """就是将几种模式的“不标准”，变成后续能够读入pandas的“简单”jsonline格式
        """
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
def generate_shell(infile, outfile, sns_context, sns_palette, x, ys):
    Plot(infile, outfile).run(
        context=sns_context, palette=sns_palette, x=x, y=ys.split(",")
    )


if __name__ == "__main__":
    cli()

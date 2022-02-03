import json
import pdb
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import click
import glom # type: ignore
import pandas as pd


class Plot:
    
    def __init__(self, infile: str, outfile: str):
        self.infile = infile
        self.outfile = outfile

    def run(self, *, context: str = "talk", palette: str = "blue"):
        import seaborn as sns # type: ignore
        sns.set_context(context)
        sns.set_palette(palette)
        
        # now finish this
        x = "epoch"



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
        with open(self.infile) as IN, open(self.outfile, 'w') as OUT:
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
            obj['wholestep'] = glom.glom(obj, 'epoch') * max_step + glom.glom(obj, 'step')
        return obj

    def run(self):
        """就是将几种模式的“不标准”，变成后续能够读入pandas的“简单”jsonline格式
        """
        max_step = -1
        # helper
        def should_ignore(temp: str) -> bool:
            return temp.startswith("#") or not temp
        
        # 1st iteration
        with open(self.infile) as IN:
            for line in IN:
                temp = line.strip()
                if should_ignore(temp):
                    continue
                parsed = json.loads(temp)
                if "step" in parsed:
                    max_step = max(parsed['step'], max_step) 

        # 2nd iteration
        with open(self.infile) as IN, open(self.outfile, 'w') as OUT:
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
@click.option("--infile", required=True)
@click.option("--outfile", required=True)
@click.option("--sns-context", default="talk")
@click.option("--sns-palette", default="blue")
def generate_shell(infile, outfile, sns_context, sns_palette):
    Plot(infile, outfile).run(context=sns_context, palette=sns_palette)


if __name__ == "__main__":
    cli()

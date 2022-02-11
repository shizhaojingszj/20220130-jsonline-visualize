nextflow.enable.dsl = 2

// also import params
include {
  run_combine_plot_workflow;
  get_helper_py;
  get_plot_jsonnet;
} from './step2'



process get_confusion_matrix_folders {
  publishDir "./data", mode: 'symlink'

  output:
    path "${params.folder_list}", emit: folder_list

  script:
    """
    #! python
    from pathlib import Path
    import re

    pat = re.compile("^config\\.1[0-7]\\.([\\d_]+)\\.json\$")
    # folder of basedir1
    file1 = Path("/mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp")
    file2 = Path("/mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp_20220210")

    def get_json_file(json_folder: Path, dir: Path) -> Path:
      return dir / "json_output" / json_folder.name

    with open("${params.folder_list}", 'w') as OUT:
      for folder in sorted(file1.iterdir()):
        if pat.match(folder.name):
          # glob for confusion_matrix folder, a.k.a 'confuse_matrix'
          confusion_matrix_folder = list(folder.rglob("confuse_matrix"))

          # only write to output if found
          if confusion_matrix_folder:
            json_file = get_json_file(folder, file1)
            if not json_file.is_file():
              json_file = get_json_file(folder, file2)
              if not json_file.is_file():
                print(f"Cannot find json file: {json_file}")
                raise NotImplementedError("xxxx")
            print(f"{confusion_matrix_folder[0].absolute()}\\t{json_file}", file=OUT)
          else:
            # don't fail, only warn to stdout
            print(f"Cannot find confusion_matrix folder in {folder}")
        else:
          # debug purpose
          print(f"skip {folder.absolute()}")
    """

}


process get_confusion_matrix_folders2 {
  publishDir "./data", mode: 'symlink'

  output:
    path "${params.folder_list}", emit: folder_list

  script:
    """
    #! python
    from pathlib import Path
    import re

    pat = re.compile("^config\\.1[0-7]\\.([\\d_]+)\\.json\$")
    # folder of basedir1
    file1 = Path("/mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp")
    file2 = Path("/mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp_20220210")

    def get_json_file(json_folder: Path, dir: Path) -> Path:
      return dir / "json_output" / json_folder.name

    def is_bad(json_file: Path) -> bool:
      return (
        json_file.parent.parent == file1 and
        json_file.name[len("config."):(len("config.")+2)] in ["10", "11", "12", "13"]
      )

    assert is_bad(file1 / "json_output" / "config.10")

    with open("${params.folder_list}", 'w') as OUT:
      for folder in sorted(file1.iterdir()):
        if pat.match(folder.name):
          # glob for confusion_matrix folder, a.k.a 'confuse_matrix'
          confusion_matrix_folder = list(folder.rglob("confuse_matrix"))

          # only write to output if found
          if confusion_matrix_folder:
            json_file = get_json_file(folder, file1)
            if not json_file.is_file():
              json_file = get_json_file(folder, file2)
              if not json_file.is_file():
                print(f"Cannot find json file: {json_file}")
                raise NotImplementedError("xxxx")
            if not is_bad(json_file):
              print(f"{confusion_matrix_folder[0].absolute()}\\t{json_file}", file=OUT)
          else:
            # don't fail, only warn to stdout
            print(f"Cannot find confusion_matrix folder in {folder}")
        else:
          # debug purpose
          print(f"skip {folder.absolute()}")
    """

}


workflow run_combine_plot {

  def helper_py = get_helper_py()
  def plot_jsonnet = get_plot_jsonnet()

  get_confusion_matrix_folders()

  get_confusion_matrix_folders.out.folder_list.view {
    println "File ${it} created."
    "-------------folder_list"
  }

  run_combine_plot_workflow(
    get_confusion_matrix_folders.out.folder_list,
    helper_py,
    plot_jsonnet,
  )
}


workflow run_combine_plot_only_bug_fixed_8 {
  def helper_py = get_helper_py()
  def plot_jsonnet = get_plot_jsonnet()

  get_confusion_matrix_folders2()

  get_confusion_matrix_folders2.out.folder_list.view {
    println "File ${it} created."
    "-------------folder_list"
  }

  run_combine_plot_workflow(
    get_confusion_matrix_folders2.out.folder_list,
    helper_py,
    plot_jsonnet,
  )
}

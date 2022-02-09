nextflow.enable.dsl = 2

include { 
  convert_csv_files_to_jsonline; 
  plot_files as single_folder_plot;
  get_helper_py;
} from './step1'


process get_confusion_matrix_folders {
  publishDir "./data", mode: 'symlink'

  output:
    path "folder.list", emit: folder_list

  script:
    """
    #! python
    from pathlib import Path
    import re

    pat = re.compile("^config\\.1[0-7]\\.([\\d_]+)\\.json\$")
    # folder of basedir
    file1 = Path("/mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp")

    def get_json_file(json_folder: Path) -> Path:
      return file1 / "json_output" / json_folder.name

    with open("folder.list", 'w') as OUT:
      for folder in sorted(file1.iterdir()):
        if pat.match(folder.name):
          # glob for confusion_matrix folder, a.k.a 'confuse_matrix'
          confusion_matrix_folder = list(folder.rglob("confuse_matrix"))

          # only write to output if found
          if confusion_matrix_folder:
            json_file = get_json_file(folder)
            if not json_file.is_file():
              print(f"Cannot find json file: {json_file}")
            print(f"{confusion_matrix_folder[0].absolute()}\\t{json_file}", file=OUT)
          else:
            # don't fail, only warn to stdout
            print(f"Cannot find confusion_matrix folder in {folder}")
        else:
          # debug purpose
          print(f"skip {folder.absolute()}")
    """

}


process combine_plot {
  input:
    file folder_list

  script:
    """
    echo ${folder_list}
    """
}


workflow single_plots_each_folder {
  def helper_py = get_helper_py()

  get_confusion_matrix_folders()
  // 使用flatMap读取了folder_list这个文件
  // 并将每行的第一个field（也就是confusion_matrix_folder）作为单个item导入到dataflow中
  get_confusion_matrix_folders.out.folder_list.flatMap {
    // 一个一个的结果
    folder_list -> 
    def a = new File(folder_list.toString()).text.split("\n")
    a*.split("\t")
  }.set { line_fields }

  // 每一个folder，都计算jsonlines
  line_fields.map {
    it ->
      def (cf_folder, json_file) = it
      // output 
      def baseName = new File(json_file).name
      // use list as tuple, must specify file(cf_folder)
      [file(cf_folder), "${baseName}.cf_jsonline"]
  }.set {
    abc
  }

  abc.view()

  convert_csv_files_to_jsonline(abc, helper_py)

  single_folder_plot(
    convert_csv_files_to_jsonline.out.jsonline_file, helper_py
  )

}


workflow {
  get_confusion_matrix_folders()
  get_confusion_matrix_folders.out.folder_list.view {
    // new File(it.toString()).text.split("\n").each {
    //   println it
    // }
    // 1
    println "File ${it} created."
  }
  combine_plot(get_confusion_matrix_folders.out.folder_list)
}

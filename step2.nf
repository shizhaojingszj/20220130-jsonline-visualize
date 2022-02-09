nextflow.enable.dsl = 2

params.subset_specs = "optimizer_name scheduler_name"

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


process subset_json {
  publishDir "./data", mode: 'symlink'

  input:
    tuple file(json_file), val(outfile)
    file python_script
  
  output:
    file("subset_json/${outfile}")

  script:
    """
    mkdir subset_json

    python ${python_script} subset-json -i ${json_file} -o subset_json/${outfile} ${params.subset_specs}
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
      String jsonline_file_basename = "${baseName}.cf_jsonline"
      [file(cf_folder), jsonline_file_basename]
  }.set {
    // 是给`process:convert_csv_files_to_jsonline`的输入
    for_convert
  }

  line_fields.map {
    it -> 
      def (cf_folder, json_file) = it
      // output 
      def baseName = new File(json_file).name
      String subset_json = "${baseName}.subset.json"
      [baseName, json_file, subset_json]
  }.set {
    for_join
  }

  convert_csv_files_to_jsonline(for_convert, helper_py)

  convert_csv_files_to_jsonline.out.jsonline_file.map {
    // prepare for join, key is json file base name
    jsonline_file -> 
      def baseName = new File(jsonline_file.toString()).name - ".cf_jsonline"
      [baseName, jsonline_file]
  }.join(for_join, failOnDuplicate: true, failOnMismatch: true)
  .set {
    // after join, should be [json_file_basename, jsonline_file, json_file, subset_json]
    all_info
  }

  all_info.view {
    it ->
    def (json_file_basename, jsonline_file, json_file, subset_json) = it
    [json_file_basename, jsonline_file, json_file, subset_json].each {
      println "${it}, ${it.class}" 
    }
    "---------all_info"
  }

  // json文件中的某些信息要拿出来变成一个新的小json文件
  all_info.map {
    it ->
      def (json_file_basename, jsonline_file, json_file, subset_json) = it
      // `process:subset_json` 的第一个参数
      [file(json_file), subset_json]
  }.set {
    for_subset_json
  }

  subset_json(for_subset_json, helper_py)

  // 获取`process:single_folder_plot`的第一个参数
  subset_json.out.map {
    subset_json_file ->
      def baseName = new File(subset_json_file.toString()).name - ".subset.json"
      [baseName, subset_json_file]
  }.join(all_info).map{
    it ->
      def (String json_file_basename, subset_json_file, json_line_file, json_file, String subset_json) = it
      // `process:single_folder_plot`的第一个参数
      [json_line_file, subset_json_file]
  }.set {
    for_plot
  }

  for_plot.view {
    it -> 
      println "${it}, for_plot"
      def (json_line_file, subset_json_file) = it
      [subset_json_file, json_line_file].each {
        println "${it}, ${it.class}" 
      }
      "---------for_plot"
  }

  single_folder_plot(
    for_plot, helper_py
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

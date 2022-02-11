nextflow.enable.dsl = 2


// params
params.palette = "Reds"


// script Dir
scriptDir = new File(workflow.scriptFile.toString()).parent
println("scriptDir=${scriptDir}")
// helper.py
helper_py = file(new File(scriptDir, './helper.py').canonicalPath)
plot_jsonnet = file(new File(scriptDir, './plot.jsonnet').canonicalPath)

def get_helper_py() {
  helper_py
}

def get_plot_jsonnet(){
  plot_jsonnet
}


process convert_csv_files_to_jsonline {
  publishDir "./data", mode: 'symlink'

	input:
    tuple file(input_csv_dir), val(outfile)
    file python_script

  output:
    path "${outfile}", emit: jsonline_file

  script:

    """
    python ${python_script} from-confusion-matrix-to-jsonline \
      -i ${input_csv_dir} -o ${outfile}
    """

}


process plot_files {
  publishDir "./data", mode: 'symlink'

  input:
    tuple file(info_txt), file(other_info) // `other_info` can be /dev/null or real json info file
    file python_script

  output:
    file "${info_txt}.png"

  script:
    println(info_txt)
    def other_info_cli = ""
    // if filename is null, then don't do anything
    if(other_info.name != "null") {
      other_info_cli = "${other_info}"
    }
    println("other_info_cli: ${other_info_cli}")

    """
    python ${python_script} plot-jsonline \
      -i ${info_txt} -o ${info_txt}.png \
      --class-name Plot2 \
      --ys acc,normal_acc,luad_acc,lusc_acc \
      -x epoch \
      --sns-palette ${params.palette} \
      ${other_info_cli}
    """

}


workflow {
  // e.g. /mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp/config.5.20220207_175258.json/ckpt/inceptionv3_class3_0207/tile299/confuse_matrix
  def csv_dir = file(params.csv_dir)
  a = Channel.of([
    [csv_dir, "out.jsonline"]
  ])
  convert_csv_files_to_jsonline(
    a, helper_py
  )
  plot_files(
    convert_csv_files_to_jsonline.out.jsonline_file, helper_py, file("/dev/null")
  )
}
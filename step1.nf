nextflow.enable.dsl = 2

// script Dir
scriptDir = new File(workflow.scriptFile.toString()).parent
println("scriptDir=${scriptDir}")
// helper.py
helper_py = file(new File(scriptDir, './helper.py').canonicalPath)

// e.g. /mnt/GPU1-raid0/zhaomeng-from-GPU3/projects/20220128-fl/Federated_learning/Tdeeppath/temp/config.5.20220207_175258.json/ckpt/inceptionv3_class3_0207/tile299/confuse_matrix
csv_dir = file(params.csv_dir)


process convert_csv_files_to_jsonline {
  publishDir "./data", mode: 'symlink'

	input:
    file input_csv_dir
    file python_script
    val outfile

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
    file info_txt
    file python_script

  output:
    file "${info_txt}.png"

  script:
    println(info_txt)

    """
    mypy ${python_script}
    python ${python_script} plot-jsonline \
      -i ${info_txt} -o ${info_txt}.png \
      --class-name Plot2 \
      --ys acc,normal_acc,luad_acc,lusc_acc \
      -x epoch
    """
}


workflow {
  convert_csv_files_to_jsonline(
    csv_dir, helper_py, "out.jsonline"
  )
  plot_files(
    convert_csv_files_to_jsonline.out.jsonline_file, helper_py
  )
}
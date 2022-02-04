info_from_GPU3 = file 'info-from-GPU3.txt'
helper_py = file './helper.py'

process 'convert file path for GPU1' {
  publishDir "./data", mode: 'symlink'

  input:
    file info_from_GPU3    

  output:
    file 'info.txt' into info_txt

  script:
    """
    sed 's|/mnt/GPU1-raid0/|/mnt/raid0/zhaomeng/20210928-for-licui/|g' ${info_from_GPU3} | sed 's|"||g' > info.txt
    """
}


process 'get all filenames from info.txt' {

  publishDir "./data", mode: 'symlink'

  input:
    file info_txt

  output:
    // 将每行的文件都link到abc子文件夹下
    file 'abc/*' into single_files

  shell:
    """
    mkdir abc
    # see https://stackoverflow.com/questions/12916352/shell-script-read-missing-last-line
    while IFS= read line || [ -n "\$line" ]; do
      ln -s "\$line" abc/
    done < !{info_txt}
    """

}


process 'normalize to NEW formats' {

  publishDir "./data", mode: 'symlink'

  input:
    file info_txt from single_files.flatten()
    file python_script from helper_py
  
  output:
    file "${info_txt}.testout" into normalized_txt
  
  script:

    println(info_txt)
    println(info_txt.class)

    """
    mypy ${python_script}
    python ${python_script} normalize-old-formats -i ${info_txt} -o ${info_txt}.testout
    """
}


process 'rescue normlized files' {
  publishDir "./data", mode: 'symlink'

  input:
    file info_txt from normalized_txt 
    file python_script from helper_py

  output:
    file "${info_txt}.rescued" into rescued_txt

  script:

    println(info_txt)
    println(info_txt.class)

    """
    mypy ${python_script}
    python ${python_script} rescue-normalized-file -i ${info_txt} -o ${info_txt}.rescued
    """
}


process 'plot files' {
  publishDir "./data", mode: 'symlink'

  input:
    file info_txt from rescued_txt
    file python_script from helper_py

  output:
    file "${info_txt}.png" into png_files

  script:
    println(info_txt)

    """
    mypy ${python_script}
    python ${python_script} plot-jsonline -i ${info_txt} -o ${info_txt}.png
    """
}


png_files.view {
  println it
}
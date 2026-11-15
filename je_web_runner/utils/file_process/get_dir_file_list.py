from os import getcwd, walk
from os.path import abspath, join


def get_dir_files_as_list(dir_path: str | None = None, default_search_file_extension: str = ".json") -> list[str]:
    """
    取得指定資料夾下（含子資料夾）所有符合副檔名的檔案清單
    Get all files below a directory, subdirectories included, that end with the given extension

    :param dir_path: 要搜尋的資料夾路徑 (預設為呼叫當下的工作目錄)
                     Directory path to search (default: the working directory at the time of the call)
    :param default_search_file_extension: 要搜尋的副檔名 (預設為 ".json")
                                          File extension to search (default: ".json")
    :return: 若無符合則回傳空清單，否則回傳檔案完整路徑清單
             [] if no files found, otherwise [file1, file2, ...] with absolute paths
    """
    search_root = getcwd() if dir_path is None else dir_path
    return [
        abspath(join(root, file))  # 以檔案所在的資料夾組路徑 / Join to the directory the file is in
        for root, _dirs, files in walk(search_root)  # 遍歷資料夾 / Walk through directory
        for file in files
        if file.endswith(default_search_file_extension.lower())  # 篩選符合副檔名的檔案 / Filter by extension
    ]

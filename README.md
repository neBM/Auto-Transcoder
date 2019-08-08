# [Auto-Compressor](https://hub.docker.com/r/nebmartin/autocompressor)
# Env
- autoYes="<True/False>"
    If set to "True" then the program wont require user confirmation (Default: False).
- loop="<False/0-MAXINT>"
    False to disable checking for new files (Default).
    N to check every n minutes. Must be while numers.
- watch="</data/watch/folder/here>"
    Directory in container checks for new files. Required.
- export="</data/export/folder/here>"
    Directory in container where files are transcoded. Required.
- processed="</data/processed/file/here>.tsv"
    Directory in container where a TSV file containing already processed files is. Required.
- mvold="<False//data/watch/folder/here>"
    Directory to move the files found in the watch folder after completion.
    False to disable moving after completion (Default).
- tmp="<False//data/watch/folder/here>"
    Intermedary directory to store transcoding files. Completed files will be moved from tmp to the export directory.

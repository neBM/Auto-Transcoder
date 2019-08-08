# [Auto-Compressor](https://hub.docker.com/r/nebmartin/autocompressor)
## Env
Name | Description
--- | ---
autoYes="<True/False>" | If set to "True" then the program wont require user confirmation (Default: False).
loop="<False/0-MAXINT>" | False to disable checking for new files (Default).<br>N to check every n minutes. Must be while numers.
watch="</data/watch/folder/here>" | Directory in container checks for new files. Required.
export="</data/export/folder/here>" | Directory in container where files are transcoded. Required.
processed="</data/processed/file/here>.tsv" | Directory in container where a TSV file containing already processed files is. Required.
mvold="<False//data/watch/folder/here>" | Directory to move the files found in the watch folder after completion.<br>False to disable moving after completion (Default).
tmp="<False//data/watch/folder/here>" | Intermedary directory to store transcoding files. Completed files will be moved from tmp to the export directory.


## Examples
`docker run -v /mnt/compressor:/data -v /mnt/compressor_config:/config -e watch="/data/compressor/inbox" -e export="/data/compressor/outbox" -e mvold="False" -e autoYes="True" -e loop="1" -e tmp="/data/compressor/tmp" -e processed="/config/processed.tsv" -it autocompressor`

Take files from `/mnt/compressor/inbox`, compressing the files in `/mnt/compressor/tmp`, save them to `/mnt/compressor/outbox/` and updating `/config/processed.tsv` with the inbox files directory checking the inbox every 1 minute without asking confirmations from STDIN.

---
`docker run -v /mnt/compressor:/data -v /mnt/compressor_config:/config -e watch="/data/compressor/inbox" -e export="/data/compressor/outbox" -e mvold="/data/compressor/old" -e autoYes="False" -e loop="False" -e tmp="False" -e processed="/config/processed.tsv" -it --rm autocompressor`

Take files from `/mnt/compressor/inbox`, compressing the files in `/mnt/compressor/outbox/` and updating `/config/processed.tsv` with the inbox files directory checking the inbox once and then closing and deleting the container while asking for confirmations from STDIN. Once completed compression, the inbox files get moved to `/data/compressor/old`.

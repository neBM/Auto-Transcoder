FROM ubuntu
WORKDIR /usr/src/app
RUN apt update && apt install --no-install-recommends -y \
python3 \
ffmpeg \
&& rm -rf /var/lib/apt/lists/*
COPY . .
CMD [ "python3", "./main.py" ]

FROM joyzoursky/python-chromedriver:latest

RUN apt-get update
RUN mkdir /haxss
RUN cd /haxss
COPY ./ /haxss/

RUN pip install stable_baselines3==1.3.0
RUN pip install selenium==3.141.0
RUN pip install esprima==4.0.1
RUN pip install gym==0.18.3
RUN pip install seaborn==0.12.0
RUN pip install lxml==4.9.1
RUN pip install beautifulsoup4==4.11.1
RUN pip install diff_match_patch
RUN pip install torch==1.11.0s
RUN pip install requests==2.28.1
RUN pip install art==5.7

WORKDIR /haxss

ENTRYPOINT /bin/bash
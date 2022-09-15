       )                )   (      (     
    ( /(     (       ( /(   )\ )   )\ )  
     )\())    )\      )\()) (()/(  (()/(  
    ((_)\  ((((_)(   ((_)\   /(_))  /(_)) 
     _((_)  )\ _ )\  __((_) (_))   (_))   
    | || |  (_)_\(_) \ \/ / / __|  / __|  
    | __ |   / _ \    >  <  \__ \  \__ \  
    |_||_|  /_/ \_\  /_/\_\ |___/  |___/  

##A reinforcement learning based XSS injection prototype.


haxss docker


from docker hub:

	docker run -it --name haxss --network=host mlf20/haxss

build from Dockerfile:
    
    git clone https://github.com/ICL-ml4csec/HAXSS.git
    cd ./HAXSS
    docker build -t haxss .
    docker run -it --name haxss --network=host haxss bash

train haxss with: 

    python train.py --url [url]

test haxss with:

     python test.py --url [url]



Do not run apt-get upgrade in the docker contianer as this will update the chrome version, causing the chromedrive to be the wrong version.

The Micro Benchmark used to train Haxss can be found in the 'micro_benchmark' folder, which can be made into a container as described in the relevant README.md

The following webapps can be built into docker containers:  
- WebSecLab 
- WAVSEP
- WackoPicko   
- SCARF

These are located in the folder 'webapp_dockers', and can be found with corresponding README.md files.

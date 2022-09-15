from tomcat:9

RUN apt-get update

RUN apt-get install -y wget
RUN apt-get install -y unzip


ADD https://downloads.sourceforge.net/project/wavsep/WAVSEP-v1.5/wavsep.war?ts=gAAAAABhhTYLIvgR5PzPYM12WbhlCQycWRdCNi-_DB7k9cAjng3fATphLbP7peBUa9kn53o65P_ziuBdqzo3MXhQ7Z2Bz3iSPg%3D%3D&r=https%3A%2F%2Fsourceforge.net%2Fprojects%2Fwavsep%2Ffiles%2FWAVSEP-v1.5%2Fwavsep.war%2Fdownload /usr/local/tomcat/webapps/wavsep.war

EXPOSE 8080
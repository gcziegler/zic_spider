'''
Created on Sep 26, 2017
@author: guillermo.ziegler
Version 0.8

* usar el contenido de BeautifulSoup directamente sin procesar el content
* Usar make_file en vez de make_table


'''
#For System Exit
import sys
#date time
import datetime

#Config Parse to read conf file
import configparser
config = configparser.ConfigParser(allow_no_value=True)
config.read("zic_spider.conf")
#Logging
LOG_FILE = config['logging']['file']
LOG_FORM = config['logging']['format']
LOG_LVL = config['logging']['level']
#Data
BSLN_FILES_FLDR = config['data']['baseline_files_folder']
URLS_CSV = config['data']['urls_CSV']
URLS_CSV_FLDR = config['data']['urls_CSV_folder']
#Diff Ratio
#Cuanto estoy dispuesto a tolerar de diferencia en la comparacion 0 a 1. Mas cerca de 1 mas parecidos son los archivos
DIFF_RATIO = float(config['diffs']['acceptable_ratio'])
#Email
EMAIL_SMTP = config['email']['smtp']
EMAIL_PORT = config['email']['port']
EMAIL_FROM = config['email']['from']
EMAIL_TO = config['email']['to']
EMAIL_USR = config['email']['usr']
EMAIL_PWD = config['email']['pwd']
EMAIL_SBJ = config['email']['subject'] + " " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

#Logging file
import logging
logging.basicConfig(filename=LOG_FILE,format=LOG_FORM,level=LOG_LVL)

#To read CSV file for dict
import csv

#Import para mover y rename files
import os

# Import requests (to download the page)
import requests
# set the headers like we are a browser,
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

# Import BeautifulSoup (to parse what we download)
from bs4 import BeautifulSoup

#Import Path handling lib
from pathlib import Path

#Baseline Files
DATA_DIR = Path('.', BSLN_FILES_FLDR)
DATA_DIR.mkdir(exist_ok=True, parents=True)

#Tempo File
TEMPO_FILE = 'tempo.txt'
TEMPO_FNAME = DATA_DIR.joinpath(Path(TEMPO_FILE).name)

#Dict File
DATA_DIR_DICT = Path('.', URLS_CSV_FLDR)
DICT_FILE=URLS_CSV
DICT_FNAME = DATA_DIR_DICT.joinpath(Path(DICT_FILE).name)

#If DICT_FILE does NOT exist, stop exeecution with error
if DICT_FNAME.exists() == False:
    logging.error("Dictionary File DOES NOT exist. Terminating!!")
    sys.exit("Dictionary File DOES NOT exist. Terminating")

#Import library for diffs
import difflib

#library for email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
MAIL_USER = EMAIL_USR
MAIL_PWD = EMAIL_PWD

#Email Setup
#Preparo Email
msg = MIMEMultipart('alternative')
msg['From'] = EMAIL_FROM
msg['To'] = EMAIL_TO
msg['Subject'] = EMAIL_SBJ

message_top = """\
<html>
    <head></head>
    <body>
"""
message_mid = ""
message_end = """\
    </body>
</html>
"""

# set the url to read
url_dict  = {}
with open(DICT_FNAME, 'r') as f:
    readCSV = csv.reader(f, delimiter=',')
    for line in readCSV:
        name = line[0]
        url = line[1]
        url_dict[name] = url

logging.info('********************************************************************************')
logging.info('*** STARTING PROCESS ***')
logging.info('********************************************************************************')
#enter the loop
for url in url_dict:
    logging.info("Processing: %s => %s", url, url_dict[url])
    # download the homepage
    logging.info("Requesting: %s", url)
    response = requests.get(url_dict[url], headers=headers)
    
    #si no vuelve 200 (OK) => Aviso y sigo con el próximo
    if response.status_code != requests.codes.ok:  # @UndefinedVariable
        logging.info("Errore reading %s", url_dict[url])
        logging.info("URL Returned %s", response.status_code)
        logging.info("********************************************************************************")
        logging.info("Preparing Warning messAge for final report email")
        message_mid = message_mid + """<h3>""" + url + """</h3>""" 
        message_mid = message_mid + """\
        <p>
            Error reading  """ + url_dict[url] + """<br>\
            URL returned """ + str(response.status_code) + """<br>\
        </p>
        """        
        continue #sigo con next URL 

    #El sitio fue leido con exito
    #parse the downloaded homepage and grab all text, then,
    logging.info("Parsing Response and extracting content")
    soup = BeautifulSoup(response.text, "html.parser")
    '''
    usar el contenido de BeautifulSoup directamente sin procesar el content
    content = soup.body.get_text()
        
    #remove empty lines from content
    while '\n\n' in content:
        content=content.replace('\n\n','\n')
    '''
    content = str(soup) 
    
    #¿Existe baseline file?
    BASE_FILE = url + ".txt"
    DATA_DIR = Path('.', 'spdrfls')
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    BASE_FNAME = DATA_DIR.joinpath(Path(BASE_FILE).name)

    #baseline_file = Path(url + ".txt")
    logging.info("Checking if Baseline file %s exists", BASE_FNAME)  #baseline_file)
    if BASE_FNAME.exists():   #baseline_file.exists():
        # Baseline File Exists => Creo tempo.txt para hacer comparación
        logging.info("Baseline file for %s DOES exist. Creating Tempo file", url)        
        tempo = open(TEMPO_FNAME,"w", encoding="utf-8") 
        tempo.write(content)
        tempo.close()
        # Comparo el contenido de tempo.txt contra el "baseline file" que ya tenía
        logging.info("Comparing Tempo vs Baseline file %s", BASE_FNAME) #baseline_file)
        tmp_text = open(TEMPO_FNAME, encoding="utf8").readlines()
        bsln_text = open(BASE_FNAME, encoding="utf8").readlines()   #baseline_file
        #evalúo si hay diferencias para reportar
        #Usando SequenceMatcher ratio. Si devuelve mas de lo que acepto en RATIO entonces son close matches
        logging.info("Evaluating differences ratio")        
        s = difflib.SequenceMatcher(None, tmp_text, bsln_text)
        if s.ratio() < DIFF_RATIO:
            #El factor de diferencias es menos del RATIO definido
            logging.info("Ratio is %s and is less than defined RATIO of %s", s.ratio(), DIFF_RATIO)
            logging.info("Reporting differences")
            #Hay que reportar las diferencias
            #Generar HTML para cuerpo del mail
            logging.info("Creating HTML for email body")
            differ = difflib.HtmlDiff(4, 50)
            '''
            * Usar make_file en vez de make_table
            diff_html = differ.make_table(tmp_text, bsln_text, "Now", "Before", context=True, numlines=3)
            '''
            diff_html = differ.make_file(tmp_text, bsln_text, "Cambio", "Baseline", context=True, numlines=3)
            
            message_mid = message_mid + """\
            <br>\
            <h3>""" + url + """</h3>
            <br>\
            """
            message_mid = message_mid + diff_html
            logging.info("Info added to Message")
            #Reemplazar baseline con tempo
            logging.info("Creating New Baseline File with Tempo content")
            #Remove Baseline
            logging.info("Removing Baseline file %s", BASE_FNAME)   #baseline_file)
            os.remove(BASE_FNAME)   #baseline_file)
            #Rename tempo as baseline
            logging.info("Renaming Tempo as Baseline")
            os.rename(TEMPO_FNAME, BASE_FNAME)  #baseline_file)
        else:
            logging.info("Ratio is %s and is GREATER THAN min acceptable Ratio of %s.", s.ratio(), DIFF_RATIO)
            logging.info("Nothing to report")
    else:
        #Baseline file DOES NOT exist. Creo el archivo para la proxima vez
        logging.info("Baseline file for %s DOES NOT exist. Creating...", url)        
        baseline_file = open(BASE_FNAME,"w", encoding="utf-8") 
        baseline_file.write(content)
        baseline_file.close()
        logging.info("Baseline file for %s Created", url)
        logging.info("DONE PROCESSING %s", url)
        logging.info("********************************************************************")        
        continue
    logging.info("DONE PROCESSING %s", url)
    logging.info("*********************************************************************")

#SENDING EMAIL ONLY IS MSG MID IS NOT NULL
if not message_mid:
    logging.info("Nothing to send")
    logging.info("*********************************************************************")
else:
    logging.info("Sending Email w/Report")
    logging.info("*********************************************************************")

    #Preparing Msg    
    message = message_top + message_mid + message_end 
    msg.attach( MIMEText(message, 'html'))
    #Sending Msg
    mailserver = smtplib.SMTP(EMAIL_SMTP,EMAIL_PORT)
    # identify ourselves to smtp gmail client
    mailserver.ehlo()
    # secure our email with tls encryption
    mailserver.starttls()
    # re-identify ourselves as an encrypted connection
    mailserver.ehlo()
    mailserver.login(MAIL_USER, MAIL_PWD)
    mailserver.sendmail(EMAIL_FROM ,EMAIL_TO,msg.as_string())
    mailserver.quit()
    logging.info("Email Sent. Moving On...")
    logging.info("*********************************************************************")

logging.info('*** FINNISHED PROCESS ***')
logging.info("*********************************************************************")



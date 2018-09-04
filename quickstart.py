from __future__ import print_function
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import json
import os
from pymongo import MongoClient

# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/gmail.modify'
userId = 'me'
client = MongoClient('localhost', 27017)
db = client['emailDatabase']
collection = db['emailCollection']



store = file.Storage('token.json')
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
    creds = tools.run_flow(flow, store)
service = build('gmail', 'v1', http=creds.authorize(Http()))


def setSubject(rule,queryParams):

    subjectList = rule.get('subject')
    if type(subjectList) == list:
        setList("subject:",subjectList,queryParams)
    else:
        queryParams.append("subject:"+subjectList+" ")
    return queryParams

def setFrom(rule,queryParams):

    fromList = rule.get('from')
    if type(fromList) == list:
        setList("from:",fromList,queryParams)
    else:
        queryParams.append("from:"+fromList+" ")
    return queryParams

def setList(suffix,List,queryParams):
    for param in List:
        newParam = suffix + param + " "
        queryParams.append(newParam)


def formQueryForSearch(rule,queryParams):
    setFrom(rule,queryParams)
    setSubject(rule,queryParams)
    queryForSearch = " ".join(queryParams)
    queryForSearch = "{"+queryForSearch+"}"
    #print(queryForSearch)
    return queryForSearch


def readRules():

    dir_path = os.path.dirname(__file__)
    jsonfile = os.path.join(dir_path, '/home/nithin/email/rules.json')
    with open(jsonfile, 'r') as f:
        data = json.load(f)
        rules = data.get('rules')
        for rule in rules:
            query=""
            queryParams = []
            dataForEachMail = {}

            labelIds = fetchRequiredLabelIds(rule)
            query = formQueryForSearch(rule,queryParams)
            performAction(userId,rule,query,labelIds)
            getMessages(userId,query,dataForEachMail,labelIds)


def listOfMessages(userId,query,labelIds):
    messageIds = []
    messages = service.users().messages().list(userId=userId,q=query,labelIds=labelIds).execute()
    messagesList = messages.get('messages')
    for message in messagesList:
        messageIds.append(message.get('id'))
    return messageIds


def getMessages(userId,query,dataForEachMail,labelIds):
    messageIds = listOfMessages(userId,query,labelIds)
    for messageId in messageIds:
        setDataForEachEmail(userId,messageId,dataForEachMail)
    #print(dataForEachMail) #######
    collection.insert(dataForEachMail)

def setDataForEachEmail(userId,messageId,dataForEachMail):
        message = service.users().messages().get(userId=userId,id=messageId).execute()

        credentials = {}

        labelIds = message.get('labelIds')
        payload = message.get('payload')
        headers = payload.get('headers')

        for header in headers:

            if header['name'] == 'Subject':
                credentials.__setitem__("Subject",header['value'])

            elif header['name'] == 'Date':
                credentials.__setitem__("Date",header['value'])

            elif header['name'] == 'From':
                credentials.__setitem__("From",header['value'])

        credentials.__setitem__("LabelIds",labelIds)
        dataForEachMail.__setitem__(messageId,credentials)

def fetchRequiredLabelIds(rule):
    labelIds = rule.get('labelIds')
    return labelIds

def deleteMessage(userId,msgId):
    service.users().messages().delete(userId=userId,id=msgId).execute()

def modifyMessages(userId,rule,msgIds):
    for msgId in msgIds:
        body = {}
        addLabelIds = rule.get('addLabelIds')
        body.__setitem__("addLabelIds",addLabelIds)
        modifiedMsg = service.users().messages().modify(userId=userId, id=msgId,body=body).execute()
        print("The messages are modified by using the labels provided {}".format(str(addLabelIds)))


def listLabels(userId):
    Labels = service.users().labels().list(userId=userId).execute()
    labelsList = Labels.get('labels')
    labelsId = []
    labelsName = []
    for label in labelsList:
        labelsId.append(label.get('id'))
        labelsName.append(label.get('name'))

    return labelsId,labelsName

def listMessages(userId,query,labelIds):
    messageIds = []
    messages = service.users().messages().list(userId=userId,q=query,labelIds=labelIds).execute()
    messagesList = messages.get('messages')
    for message in messagesList:
        messageIds.append(message.get('id'))
    return messageIds



def addLabels(userId,rule,labelsId,labelsName):

    labelsToAdd = rule.get("labelsToAdd")
    for labelName in labelsToAdd:
        if labelName not in labelsName:
            label = {}
            label.__setitem__("messageListVisibility","show")
            label.__setitem__("labelListVisibility","labelShow")
            label.__setitem__("name",labelName)
            labelId = service.users().labels().create(userId=userId,body=label).execute()
            print("New Label of name {} with id {} is successfully created\nYou can now tag your email with the newly created tag\n\n".format(labelId['name'],labelId['id']))


def removeLabels(userId,rule,labelsId,labelsName):
        labelsToRemove = rule.get('labelsToRemove')

        for removeLabel in labelsToRemove:
            if removeLabel in labelsName:
                index = labelsName.index(removeLabel)
                labelId = labelsId[index]
                service.users().labels().delete(userId=userId,id=labelId).execute()
                print("Label {} is removed succcessfully".format(removeLabel))



def performAction(userId,rule,query,labelIds):
    actionType = rule.get('action')
    labelsId,labelsName = listLabels(userId)
    msgIds = listMessages(userId,query,labelIds)

    if actionType == "addLabels":
        addLabels(userId,rule,labelsId,labelsName)
    elif actionType == "removeLabels":
        removeLabels(userId,rule,labelsId,labelsName)
    elif actionType == "modifyMessages":
        modifyMessages(userId,rule,msgIds)



readRules()

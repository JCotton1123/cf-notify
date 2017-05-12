#!/usr/bin/env bash

if [ $# -lt 1 ]
then
    echo "usage: $0 <CHANNEL> <WEBHOOK> <BUCKET> [TOPIC] [PROFILE]"
    exit 1
fi

CHANNEL=$1
WEBHOOK=$2
BUCKET=$3
TOPIC=${4:-"cf-notify"}
PROFILE=${5:-"default"}

RELEASE=$(date +%Y-%m-%d-%H%M)

if [ -z $BUCKET ];
then
    echo "Please specify a bucket name";
     exit 1
fi

if [ -z $CHANNEL ];
then
    echo "Please specify a Slack Channel e.g #general or @me";
    exit 1
fi

if [ -z $WEBHOOK ];
then
    echo "Please specify a Slack WebHook";
    exit 1
fi


if [[ $(aws configure --profile $PROFILE list) && $? -ne 0 ]];
then
    exit 1
fi


if [ ${CHANNEL:0:1} != '#' ] && [ ${CHANNEL:0:1} != '@' ];
then
    echo ${CHANNEL:0:1}
    echo 'Invalid Channel. Slack channels begin with # or @'
    exit 1
fi

CHANNEL_NAME=`echo ${CHANNEL:1} | tr '[:upper:]' '[:lower:]'`

echo "Creating bucket $BUCKET"
aws s3 mb "s3://$BUCKET" --profile $PROFILE || exit 1
echo "Bucket $BUCKET created"

echo 'Creating lambda zip artifact'
zip -j cf-notify.zip src/*
echo 'Lambda artifact created'

echo 'Moving lambda artifact to S3'
aws s3 cp cf-notify.zip s3://$BUCKET/$RELEASE/cf-notify.zip --profile $PROFILE
rm cf-notify.zip
echo 'Lambda artifact moved'

echo 'Deleting existing stack if it exists'
aws cloudformation delete-stack --stack-name cf-notify || true
aws cloudformation wait stack-delete-complete --stack-name cf-notify
echo 'Stack deleted if it existed'

echo 'Creating stack'
aws cloudformation create-stack \
    --template-body file://cloudformation/cf-notify.json \
    --stack-name cf-notify \
    --capabilities CAPABILITY_IAM \
    --parameters ParameterKey=ArtifactBucket,ParameterValue=$BUCKET \
      ParameterKey=Release,ParameterValue=$RELEASE \
      ParameterKey=TopicName,ParameterValue=$TOPIC \
      ParameterKey=SlackChannel,ParameterValue=$CHANNEL \
      ParameterKey=SlackWebhook,ParameterValue=$WEBHOOK \
    --profile $PROFILE \
    --output text

if [[ $? != 0 ]];
then
    exit 1
else
    echo 'Stack created'
fi

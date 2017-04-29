# CF Notify

## What?
An AWS Lambda function that will post Cloud Formation status updates to a Slack channel via a Slack Web Hook. Additionally it will notify you of stacks that do not have notifications enabled.


## Why?
To give visibility of Cloud Formation changes to the whole team in a quick and simple manner. For example:

![example Slack messages](./misc/example.jpeg)


## How?
CF Notify has a stack of AWS resources consisting of:
 - An SNS Topic
 - CloudWatch Rule
 - A Lambda function, which uses the SNS Topic and CloudWatch Scheduled Event as event sources
 - An IAM Role to execute the Lambda function

We add the SNS Topic of CF Notify to the notification ARNs of the Stack we want to monitor.
Search for `NotificationARNs.member.N` [here](http://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_UpdateStack.html)
for more information on notification ARNs.


## Setup

To setup CF Notify, we need to do the following.

### Prerequisites
#### Slack incoming webhook
You can create an incoming webhook [here](https://my.slack.com/services/new/incoming-webhook/).


### Deploy Lambda

This is done using the script [deploy.sh](./deploy.sh).

```sh
./deploy.sh $CHANNEL $WEBHOOK $BUCKET $TOPIC $AWS_PROFILE
```

Where:
 - CHANNEL is the Slack channel or user to send messages to.
 - WEBHOOK is the Web Hook URL of an Incoming Web Hook (see https://api.slack.com/incoming-webhooks).
 - BUCKET is the S3 bucket where the Lambda artifacts are deployed.
 - TOPIC is the SNS topic name.
 - AWS_PROFILE is the aws cli profile you want to use for deploy. The default profile is "default".

`deploy.sh` will create a zip file and upload it to S3 and also create a cloud formation stack using the [template](./cloudformation/cf-notify.json).

## Usage

Once setup is complete, all you need to do now is set the notification ARN when you update any Cloud Formation stack:

```sh
SNS_ARN=`aws cloudformation describe-stacks --stack-name cf-notify-$CHANNEL | jq ".Stacks[].Outputs[].OutputValue"  | tr -d '"'`

aws cloudformation [create-stack|update-stack|delete-stack] --notification-arns $SNS_ARN
```

You should now see messages in Slack!

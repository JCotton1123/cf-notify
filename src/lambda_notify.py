import os
import json
import shlex
import urllib
import urllib2
import boto3
import re
from itertools import groupby

try:
    import slack
except ImportError:
    pass

# Mapping CloudFormation status codes to colors for Slack message attachments
# Status codes from http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-describing-stacks.html
STATUS_COLORS = {
    'CREATE_COMPLETE': 'good',
    'CREATE_IN_PROGRESS': 'good',
    'CREATE_FAILED': 'danger',
    'DELETE_COMPLETE': 'good',
    'DELETE_FAILED': 'danger',
    'DELETE_IN_PROGRESS': 'good',
    'ROLLBACK_COMPLETE': 'warning',
    'ROLLBACK_FAILED': 'danger',
    'ROLLBACK_IN_PROGRESS': 'warning',
    'UPDATE_COMPLETE': 'good',
    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS': 'good',
    'UPDATE_IN_PROGRESS': 'good',
    'UPDATE_ROLLBACK_COMPLETE': 'warning',
    'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS': 'warning',
    'UPDATE_ROLLBACK_FAILED': 'danger',
    'UPDATE_ROLLBACK_IN_PROGRESS': 'warning'
}

# List of CloudFormation status that will trigger a call to `get_stack_summary_attachment`
DESCRIBE_STACK_STATUS = [
    'CREATE_COMPLETE',
    'DELETE_IN_PROGRESS'
]

def lambda_handler(event, context):
    if is_debugging():
        print event

    partial_message = {}
    if 'source' in event and event['source'] == 'aws.events':
        partial_message = report_stacks_without_notifications()
    else:
        partial_message = report_stack_update(event)

    message = {
        'channel': get_channel(),
        'icon_emoji': ':cloud:',
        'username': 'cf-bot'
    }
    message.update(partial_message)

    if is_debugging():
        print message
    else:
        send_slack_message(message)

    return message

def report_stack_update(event):
    message = event['Records'][0]['Sns']
    sns_message = message['Message']
    cf_message = dict(token.split('=', 1) for token in shlex.split(sns_message))

    # ignore messages that do not pertain to the Stack as a whole
    if not cf_message['ResourceType'] == 'AWS::CloudFormation::Stack':
        return {}

    return get_stack_update_message(cf_message)

def report_stacks_without_notifications():
    stacks = get_stacks_without_notification_arns()
    if not stacks: return {}

    return {
      'text': 'The following stacks are not configured for notifications: ' +
              ', '.join(["\"%s\"" % s['StackName'] for s in stacks])
    }

def send_slack_message(message):
    webhook = os.environ['WEBHOOK']
    data = json.dumps(message)
    req = urllib2.Request(webhook, data, {'Content-Type': 'application/json'})
    urllib2.urlopen(req)

def get_stacks_without_notification_arns():
    stacks_without_notifications = []
    client = boto3.client('cloudformation')
    response = client.describe_stacks()
    return [s for s in response['Stacks'] if not s['NotificationARNs']]

def get_stack_update_message(cf_message):
    attachments = [
        get_stack_update_attachment(cf_message)
    ]

    if cf_message['ResourceStatus'] in DESCRIBE_STACK_STATUS:
        attachments.append(get_stack_summary_attachment(cf_message['StackName']))

    stack_url = get_stack_url(cf_message['StackId'])

    message = {
        'text': 'Stack: *{stack}* has entered status: *{status}* <{link}|(view in web console)>'.format(
                stack=cf_message['StackName'], status=cf_message['ResourceStatus'], link=stack_url),
        'attachments': attachments
    }

    channel = get_channel(cf_message['StackName'])

    if channel:
        message['channel'] = channel

    return message

def get_channel(stack_name = None):
    default = os.environ['CHANNEL'] if 'CHANNEL' in os.environ else None

    try:
        if hasattr(slack, 'CUSTOM_CHANNELS'):
            return slack.CUSTOM_CHANNELS.get(stack_name, default)
    except NameError:
        pass

    return default

def get_stack_update_attachment(cf_message):
    fields = [
      {
        'title': 'ARN',
        'value': cf_message['StackId']
      },
      {
        'title': 'User',
        'value': resolve_user_id_to_name(cf_message['PrincipalId']),
        'short': True
      },
      {
        'title': 'Timestamp',
        'value': cf_message['Timestamp'],
        'short': True
      }
    ]

    color = STATUS_COLORS.get(cf_message['ResourceStatus'], '#000000')

    return {
        'fields': fields,
        'color': color
    }

def get_stack_summary_attachment(stack_name):
    client = boto3.client('cloudformation')
    resources = client.describe_stack_resources(StackName=stack_name)
    sorted_resources = sorted(resources['StackResources'], key=lambda res: res['ResourceType'])
    grouped_resources = groupby(sorted_resources, lambda res: res['ResourceType'])
    resource_count = {key: len(list(group)) for key, group in grouped_resources}

    title = 'Breakdown of all {} resources'.format(len(resources['StackResources']))

    return {
        'fallback': title,
        'title': title,
        'fields': [{'title': 'Type {}'.format(k), 'value': 'Total {}'.format(v), 'short': True}
                   for k, v in resource_count.iteritems()]
    }

def get_stack_region(stack_id):
    regex = re.compile('arn:aws:cloudformation:(?P<region>[a-z]{2}-[a-z]{4,9}-[1-2]{1})')
    return regex.match(stack_id).group('region')

def get_stack_url(stack_id):
    region = get_stack_region(stack_id)

    query = {
        'filter': 'active',
        'tab': 'events',
        'stackId': stack_id
    }

    return ('https://{region}.console.aws.amazon.com/cloudformation/home?region={region}#/stacks?{query}'
            .format(region=region, query=urllib.urlencode(query)))

def resolve_user_id_to_name(user_id):
    client = boto3.client('iam')
    response = client.list_users()
    for user in response['Users']:
        if user['UserId'] == user_id:
            return user['UserName']
    return 'unknown (%s)' % user_id

def is_debugging():
    return 'DEBUG' in os.environ and os.environ['DEBUG']

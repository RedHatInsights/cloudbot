#!/usr/bin/env python3

import traceback
import os
import requests
import json
import sys

from slack import RTMClient

if "SLACK_API_TOKEN" not in os.environ:
    print("Need slack api token")
    sys.exit(1)

token = os.environ["SLACK_API_TOKEN"]


def get_env(key):
    if key not in os.environ:
        print(f"Please specify {key} env var")
        sys.exit(1)
    return os.environ[key]


HOST, CA, PROJECT = get_env("HOST"), get_env("CA"), get_env("PROJECT")
CHANNEL = get_env("CHANNEL")

project_file = f"{PROJECT}.json"


class Issue(object):
    def __init__(self, key, summary, status):
        self.key = key
        self.summary = summary
        self.status = status

    def to_json(self):
        return {
            "key": self.key,
            "summary": self.summary,
            "status": self.status
        }

    @classmethod
    def from_json(cls, d):
        return cls(d["key"], d["summary"], d["status"])


if os.path.exists(project_file):
    with open(project_file) as fp:
        js = [json.loads(line) for line in fp.readlines()]
        state = {i["key"]: Issue.from_json(i) for i in js}
else:
    state = {}


def get_issue(jira_id):
    url = f"https://{HOST}/rest/api/2/issue/{jira_id}"
    res = requests.get(url, verify=CA)
    if res.status_code != 200:
        raise ValueError(f"Invalid status code: {res.status_code}")

    issue = res.json()

    status = issue['fields']['status']['name']
    summary = issue['fields']['summary']
    key = issue['key']
    return Issue(key, summary, status)


def detect_jira_id(word):
    if word.startswith(f"<https://{HOST}/browse/"):
        word = word.strip("<>").split("/")[-1]
    if word.startswith("RHCLOUD-"):
        yield word


@RTMClient.run_on(event="message")
def fetch_jira(**payload):
    try:
        data = payload['data']
        web_client = payload['web_client']

        if "text" not in data:
            return

        if "user" not in data or data["user"] == client_id:
            return

        for word in data["text"].split():
            for jira_id in detect_jira_id(word):
                channel_id = data['channel']
                thread_ts = data['ts']
                issue = get_issue(jira_id)

                browse_url = f"https://{HOST}/browse/{issue.key}"
                if word.startswith("<"):
                    browse_url = ""

                r = web_client.chat_postMessage(
                    channel=channel_id,
                    text=f"{issue.key}: {issue.summary}\nStatus: *{issue.status}*\n{browse_url}",
                    thread_ts=thread_ts
                )
                print(r)
    except Exception:
        traceback.print_exc()


def fetch_client_id():
    r = requests.get(f"https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {token}"})

    if r.status_code != 200:
        return ValueError("Failed to fetch client ID")

    return r.json()["user_id"]


client_id = fetch_client_id()
slack_rtm = RTMClient(token=token)
slack_rtm.start()

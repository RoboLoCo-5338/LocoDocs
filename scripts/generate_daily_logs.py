## this script is run every day at midnight
## first it pulls all the meeting dates from google calendar
## then it generates a log for each meeting date
## it adds the log to the database through the graphql API

import gql.transport
import gql.transport.aiohttp
import requests
import json
from ics import Calendar
from datetime import datetime, timedelta
import arrow
from gql import gql, Client, transport
import gql
import markdown as m
import dotenv
dotenv.load_dotenv()

from trender import TRender
import os

START_DATE = "3-10-2025"
SUBTEAMS = ["Software", "Mechanical", "Creative", "Business"]
WIKI_URL = "http://localhost/graphql"
from gql.transport.requests import RequestsHTTPTransport

headers = {
    "Authorization": "Bearer " + os.getenv("WIKI_API_KEY")
},
transport = RequestsHTTPTransport(url=WIKI_URL, headers=headers)
client = Client(transport=transport, fetch_schema_from_transport=True)

def overwrite_graphql_file(doc_id: int, path: str, title:str, markdown: str, tags=None):
    txt = markdown + "\n\n\n*note: due to the presence of the `auto_overwrite` tag, every change manually made to this document will be overwritten once a day at midnight. Please remove the `auto_overwrite` tag if you wish to edit this page manually. However, if this tag is on a page, its probably on there for a reason, so consult a software member first.*" 
    htmlMark = m.markdown(txt).replace("\n", "<br>").replace("\"", "\\\"")
    if tags is None:
        tags = []
    mutation = gql.gql("""
        mutation {
            pages {
                update(
                    id: {ID}
                    path: "{PATH}"
                    content: "{HTML}"
                    title: "{TITLE}"
                    editor: "ckeditor"
                    isPublished: true
                    isPrivate: false
                    locale: "en"
                    description: ""
                    tags: {TAGS}
                ) {
                    responseResult {
                        errorCode
                        message
                        slug
                        succeeded
                    }
                }
            }
        }
                       """.replace("{ID}", str(doc_id)).replace("{PATH}", path).replace("{HTML}", htmlMark).replace("{TITLE}", title).replace("{TAGS}", str(tags).replace("'", "\"")))
   
    try:
   
        result = client.execute(mutation)
        print(result)
    except:
        return False
    return True
def delete_graphql_file(doc_id: int):
    mutation = gql.gql("""
        mutation {
            pages {
                delete(
                    id: {ID}
                ) {
                    responseResult {
                        errorCode
                        message
                        slug
                        succeeded
                    }
                }
            }
        }
                       """.replace("{ID}", str(doc_id)))
   
    try:
   
        result = client.execute(mutation)
        print(result)
    except:
        return False
    return True
def set_graphql_file(path: str, title:str, markdown: str, tags=None):
    htmlMark = m.markdown(markdown).replace("\n", "<br>").replace("\"", "\\\"")
    if tags is None:
        tags = []
    mutation = gql.gql("""
        mutation {
            pages {
                create(
                    path: "{PATH}"
                    content: "{HTML}"
                    title: "{TITLE}"
                    editor: "ckeditor"
                    isPublished: true
                    isPrivate: false
                    locale: "en"
                    description: ""
                    tags: {TAGS}
                ) {
                    responseResult {
                        errorCode
                        message
                        slug
                        succeeded
                    }
                }
            }
        }
                       """.replace("{PATH}", path).replace("{HTML}", htmlMark).replace("{TITLE}", title).replace("{TAGS}", str(tags)))
   
    try:
   
        result = client.execute(mutation)
        print(result)
    except:
        return False
    return True
    
def read_document(path: str):
    gql_q = get_graphql_file(path)

    if gql_q is None:
        return None
    return gql_q['pages']['singleByPath']['content']
def get_graphql_file(path: str):

    q = """
    {
        pages {
            singleByPath(
                locale: "en"
                path: "PATHHERE"
            ) {
                id
                content
                contentType
                editor
                render
                title
                tags {
                    tag
                }
                
            }
        }
    }
    """.replace("PATHHERE", path)

    query = gql.gql(q)
    try:
        result = client.execute(query)
    except Exception as e:
        # print(path)
        # print(e)
        return None
    return result

def get_meetings():
    roboloco_calendar_raw = requests.get("https://calendar.google.com/calendar/ical/team5338%40gmail.com/public/basic.ics").text
    roboloco_calendar = Calendar(roboloco_calendar_raw)
    meetings = []
    for event in roboloco_calendar.events:
        tz = arrow.now('America/New_York').tzinfo
        start = event.begin.astimezone(tz)
        end = event.end.astimezone(tz)
        name = event.name
        ## start is 3/10/2025 just for testing
        start_date = datetime.strptime(str(START_DATE), "%m-%d-%Y").astimezone(tz)
    

        if start_date < start:
            meeting = {
                "start": start,
                "end": end,
                "name": name,
            }
        
            meetings.append(meeting)

    meetings.sort(key=lambda x: x["start"])
    return meetings

def linkify(meetings,subteam:str):
    meetings = list(map(lambda x: f"[{x}](/{subteam.lower()}/{x})", meetings))
    string = "\n".join(meetings)
    return string
def generateSubteamFiles(meetings):
    for team in SUBTEAMS:
        
        today = datetime.now().date()
        a_month_in = today.replace(day=1) - timedelta(days=15)
        a_month_out = today.replace(day=1) + timedelta(days=2)
        filtered_meetings = [meeting for meeting in meetings if shouldDoMeeting(meeting)] 
        recent_meetings = list(map(lambda x: f"{x["start"].date().strftime("%m-%d-%Y")}", [meeting for meeting in filtered_meetings if meeting["start"].date() <= a_month_out and meeting["start"].date() >= a_month_in]))
        all_meetings = list(map(lambda x: f"{x["start"].date().strftime("%m-%d-%Y")}",filtered_meetings))
        SUBTEAM_PARAMETERS = {
            "subteam": team,
            "last_generated_time": datetime.now().isoformat(),
            "all_meetings": linkify(all_meetings, team),
            "recent_meetings": linkify(recent_meetings, team),
        }
        
        for file in os.scandir("./scripts/subteam_template"):
            existent_file = get_graphql_file(f"{team.lower()}/{file.name.replace(".md", "")}") 
            
          
            autooverwrite = False
            doc_id = None
            if existent_file is not None:
                tags = existent_file['pages']['singleByPath']['tags']
          
                if tags is not None:
                    tags = list(map(lambda obj: obj['tag'], tags))
                    autooverwrite = "auto_overwrite" in tags
                    doc_id = existent_file['pages']['singleByPath']['id']
        
            if existent_file is None or autooverwrite:
               
                with open(file.path, "r") as f:
                    content = f.read().replace("#", "ѱ") ## this specific greek letter is hereby banned from the wiki, because using it will break the markdown parser
                rendered_file = TRender(content) ## the templating engine im using sees "#" as comments, so if i want to template markdown, i cant use "#". could i change templating engines? absolutely. do i care? nope.
                render=  rendered_file.render(SUBTEAM_PARAMETERS).replace("ѱ", "#")
                title = render.strip().split("\n")[0].replace("# ", "").replace("@date", "Daily Log Template")
                if existent_file is None:
                    set_graphql_file(f"{team.lower()}/{file.name.replace(".md", "")}", title, render)
                else:
                    overwrite_graphql_file(doc_id, f"{team.lower()}/{file.name.replace(".md", "")}", title, render, tags=["auto_overwrite"])

## criteria for doing meeting:
    ## it contains the string "RoboLoCo Meeting" in the title
    ## it does not contain the words "cancelled" or "canceled" in the title, or "Tenative"

def shouldDoMeeting(meeting):
    if "RoboLoCo Meeting".lower() in meeting["name"].lower() and "cancelled" not in meeting["name"].lower() and "canceled" not in meeting["name"].lower() and "tentative" not in meeting["name"].lower():
        return True
    return False

def generateDailyLogs(meetings):
    for team in SUBTEAMS:
        SUBTEAM_PARAMETERS = {
            "subteam": team,
            "last_generated_time": datetime.now().isoformat()
        }
        today = datetime.now().date()
        a_month_in = today.replace(day=1) - timedelta(days=15)
        a_month_out = today.replace(day=1) + timedelta(days=2)
        print(a_month_out)
        meetings_within_a_month = [meeting for meeting in meetings if meeting["start"].date() <= a_month_out and meeting["start"].date() >= a_month_in]
        for meeting in meetings_within_a_month:
            if shouldDoMeeting(meeting):
                template = read_document(f"{team.lower()}/daily_log_template")
                if template is None:
                    print(f"Template not found for {team}")
                    continue
                rendered_file = TRender(template)
                meeting_date = meeting["start"].date().strftime("%m-%d-%Y")
                render = rendered_file.render({
                    "subteam": team,
                    "date": meeting_date,
                    "last_generated_time": datetime.now().isoformat()
                })
                title = f"{meeting_date} - {team}"

                path = f"{team.lower()}/{meeting['start'].date().strftime('%m-%d-%Y')}"
                print("daily log path: ", path)
                # delete_graphql_file(get_graphql_file(path)["pages"]["singleByPath"]["id"]) ## used for deleting all daily logs
                set_graphql_file(path, title, render)


    return meetings_within_a_month



def main():
    meetings = get_meetings()
    generateDailyLogs(meetings)
    generateSubteamFiles(meetings)
    

if __name__ == "__main__":
    main()
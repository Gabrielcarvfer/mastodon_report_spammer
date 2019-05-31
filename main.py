#!/usr/bin/python3
from mastodon import Mastodon
from bs4 import BeautifulSoup
import os
import json
import time

######################################## Global variables ##############################################################

#Prepare global variables
spamTermsToFilter = []
punishableUsers = {}
word_dictionary = {}
punishment = "ignore" #ignore, mute, block, report, silence or ban (last two won't work without the moderation API)

######################################## Function definitions ##########################################################


def checkIfTootIsSpam(tootContent):
    global spamTermsToFilter
    spam = False
    detectedSpamTerm = ""
    for spamTerm in spamTermsToFilter:
        # Check if each spamTerm (each line of spamTermsToFilter.txt) is a substring of the content string
        if spamTerm in tootContent:
            # If it is, mark the toot as spam and stop searching for spam terms
            spam = True
            detectedSpamTerm = spamTerm
            break

    return spam, detectedSpamTerm


def collectTootMetrics(toot):
    global word_dictionary
    # Transform html into text
    content = BeautifulSoup(toot["content"], "html.parser").get_text()

    # Remove commas and hashtags
    content = content.replace("#", "")
    content = content.replace(",", "")

    # Break text by spaces
    content = content.split()

    # Count how many times words appear throughout the content and toots containing those words
    for word in content:
        if word not in word_dictionary:
            word_dictionary[word] = {"count": 1, "toots": {toot["id"]: toot}}
        else:
            word_dictionary[word]["count"] += 1
            word_dictionary[word][toot["id"]] = toot
        pass
    pass


def assembleMetricResults(word_dictionary):
    word_rank = {}
    # Rank words by frequency
    for word in word_dictionary:
        count = word_dictionary[word]["count"]
        if count not in word_rank:
            word_rank[count] = [word]
        else:
            word_rank[count] += [word]
    return word_rank


def punishableSpammer(toot, detectedSpamTerm):
    global punishableUsers

    # Get the ID of the user
    toot_user = toot["account"]["id"]

    # Save the user information and toot for later
    if toot_user not in punishableUsers:
        punishableUsers[toot_user] = {     "tootIds": [toot["id"]],
                                    "tootContents": [toot["content"]],
                                       "spamTerms": [detectedSpamTerm]}
    else:
        punishableUsers[toot_user]["tootIds"]      +=  [toot["id"]]
        punishableUsers[toot_user]["tootContents"] +=  [toot["content"]]
        punishableUsers[toot_user]["spamTerms"]    +=  [detectedSpamTerm]


def punishSpammers(punishableUsers, mastodon):
    global punishment
    for toot_user in punishableUsers:
        if punishment in "ignore":
            pass
        elif punishment is "mute":
            mastodon.account_mute(toot_user)
        elif punishment is "block":
            mastodon.account_block(toot_user)
        elif punishment is "report":
            mastodon.report(toot_user, punishableUsers[toot_user]["tootIds"], "Automatically generated report based on keywords:", ",".join(punishableUsers[toot_user]["spamTerms"]))
        elif punishment is "silence":
            pass #mastodon.moderation_silence(toot_user)
        elif punishment is "ban":
            pass #mastodon.moderation_ban(toot_user)
        else:
            #Hello there ;)
            pass
        pass
    pass

######################################## Main function #################################################################


def main():
    global punishableUsers, word_dictionary, spamTermsToFilter, punishment, mastodon

    # Load app info and user credentials
    app_data_json = "app_data.json"

    with open(app_data_json, "r") as file:
        app_data = json.load(file)

    # Check if app was already registered
    if app_data["registered"]:
        pass

    # If the app was not registered, register and create a info file
    else:
        Mastodon.create_app(
            app_data["name"],
            api_base_url=app_data["base_url"],
            to_file=app_data["name"]+'_clientcred.secret'
        )
        app_data["registered"] = True
        with open(app_data_json,"w") as file:
            json.dump(app_data, file, indent=4)

    # The current app/bot is registered at this point
    # Now to the login and access token generation

    if not os.path.exists(app_data["name"]+"_usercred.secret"):
        mastodon = Mastodon(client_id=app_data["name"]+"_clientcred.secret",
                            api_base_url=app_data["base_url"]
                            )

        mastodon.log_in(app_data["username"],
                        app_data["password"],
                        to_file=app_data["name"]+"_usercred.secret"
                        )

    # At this point, the login was done and the access token is available for use
    # Now to the toot fetching

    mastodon = Mastodon(client_id=app_data["username"],
                        client_secret=app_data["password"],
                        access_token=app_data["name"]+"_usercred.secret",
                        api_base_url=app_data["base_url"]
                        )

    # Load spam terms to filter
    with open("spamTermsToFilter.txt", "r") as file:
        spamTermsToFilter = file.readlines()

    # Remove new lines (\n things)
    for term in range(len(spamTermsToFilter)):
        spamTermsToFilter[term] = spamTermsToFilter[term].replace("\n", "")

    # Fetch most recent toots and initialize toot ID number with the maximum value
    toots_window = mastodon.timeline_local()
    last_earliest_id = 0x7FFFFFFFFFFFFFFF  #big number
    count = 0
    numTootsPerBatch = 40

    # While there are still unprocessed toots
    while len(toots_window) > 0:
        # Process each toot
        for toot in toots_window:
            # Verify if the toot is the most recent and update the earliest toot ID
            if toot["id"] < last_earliest_id:
                last_earliest_id = toot["id"]

            # Verify if the toot is a spam (only for text)
            spam, detectedSpamTerm = checkIfTootIsSpam(toot["content"])

            # If the toot is spam
            if spam:
                punishableSpammer(toot, detectedSpamTerm)

            # Collect word information for analysis
            collectTootMetrics(toot)

        # Fetch a new batch of toots earlier than the previously processed (most recent to older posts)
        toots_window = mastodon.timeline_local(max_id=last_earliest_id, limit=numTootsPerBatch)
        count += 1

        #Set the number of batches you want to process
        #if count > 10:
        #    break
    
    punishSpammers(punishableUsers, mastodon)
    
    # Assemble and print the rank of most frequent words on the analyzed toots (may help find spam)
    word_rank = assembleMetricResults(word_dictionary)

    for count in list(sorted(word_rank.keys(), reverse=True)):
        print(count, "appearences of words:", word_rank[count])

    # Dump recently punished spammers
    if len(punishableUsers) > 0:
        now = time.localtime(time.time())
        punishableUsersJson = "%d_%d_%d-punished_users.json" % (now.tm_year, now.tm_mon, now.tm_mday)
        with open(punishableUsersJson, "w") as file:
            file.write(json.dumps(punishableUsers, indent=4))

    # Fetch all spamTerms detected
    detectedSpamTerms = []
    for punishedUser in punishableUsers.values():
        detectedSpamTerms += punishedUser["spamTerms"]

    # Print number of muted/silenced users and related spam terms that triggered their silencing/muting
    print("%d spammers were %s. Detected spam terms were: %s" % (len(punishableUsers), punishment, ", ".join(detectedSpamTerms)))

    # End graciously
    return

# Execute the main function
main()
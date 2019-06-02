#!/usr/bin/python3
from mastodon import Mastodon #Provides Mastodon API
from bs4 import BeautifulSoup #Provides HTML manipulation
import os
import json
import time

######################################## Global variables ##############################################################

#Prepare global variables
spamTermsToFilter = []
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
    # Transform html into text
    content = BeautifulSoup(toot["content"], "html.parser").get_text()

    # Remove commas and hashtags
    #content = content.replace("#", "")
    #content = content.replace(",", "")

    # Break text by spaces
    content = content.split()

    # Count how many times words appear throughout the content and toots containing those words
    word_dictionary = {}
    for word in content:
        if word not in word_dictionary:
            word_dictionary[word] = {"count": 1, "toots": {toot["id"]: toot}}
        else:
            word_dictionary[word]["count"] += 1
            word_dictionary[word][toot["id"]] = toot
        pass
    pass

    return word_dictionary

def assembleMetricResults(individualTootsStatistics):
    word_dictionary = {}
    # Aggregate individual results
    for toot_word_dictionary in individualTootsStatistics:
        for word in toot_word_dictionary:
            if word not in word_dictionary:
                word_dictionary[word] = toot_word_dictionary[word]
            else:
                word_dictionary[word]["count"] += toot_word_dictionary[word]["count"]
                for toot in toot_word_dictionary[word]["toots"]:
                    word_dictionary[word]["toots"][toot] = toot_word_dictionary[word]["toots"][toot]
        pass

    word_rank = {}
    # Rank words by frequency
    for word in word_dictionary:
        count = word_dictionary[word]["count"]
        if count not in word_rank:
            word_rank[count] = [word]
        else:
            word_rank[count] += [word]
        pass
    return word_rank


def punishableSpammer(toot, detectedSpamTerm):
    # Save the user information and toot for later
    infringingContent = {     "tootId": toot["id"],
                         "tootContent": toot["content"],
                            "spamTerm": detectedSpamTerm}
    return infringingContent


def punishSpammers(punishment, punishableUsers, mastodonInstance):
    for toot_user in punishableUsers:
        # Collect all infrinding toot_ids and spam_terms for each given user
        infringingTootIds = [toot["tootId"] for toot in punishableUsers[toot_user]]
        infringingSpamTerms = [toot["spamTerm"] for toot in punishableUsers[toot_user]]

        if punishment in "ignore":
            pass
        elif punishment is "mute":
            mastodonInstance.account_mute(toot_user)
        elif punishment is "block":
            mastodonInstance.account_block(toot_user)
        elif punishment is "report":
            mastodonInstance.report(toot_user, infringingTootIds, "Automatically generated report based on keywords:" + ",".join(infringingSpamTerms))
        elif punishment is "silence":
            pass #mastodonInstance.moderation_silence(toot_user)
        elif punishment is "ban":
            pass #mastodonInstance.moderation_ban(toot_user)
        else:
            #Hello there ;)
            pass
        pass
    pass


# Fetch toots within a given tootId interval
def fetchTimeline(app_data, maxId, minId=0, maxToots=1000, mastodonInstance=None):
    if mastodonInstance is None:
        mastodonInstance = Mastodon(client_id=app_data["username"],
                                    client_secret=app_data["password"],
                                    access_token=app_data["name"] + "_usercred.secret",
                                    api_base_url=app_data["base_url"]
                                    )
    toots = []
    try:
        last_earliest_id = maxId
        toots += mastodonInstance.timeline_local(max_id=last_earliest_id, limit=40)

        while len(toots) > 0 and len(toots) < maxToots and toots[-1]["id"] < last_earliest_id and toots[-1]["id"] > minId:
            last_earliest_id = toots[-1]["id"]
            toots += mastodonInstance.timeline_local(max_id=last_earliest_id, limit=40)

    except:
        pass
    return toots


# Fetch toots in parallel
def fetchToots(maxBatches, mastodonInstance, app_data):
    threadToots = mastodonInstance.timeline_local()

    # Store the earliest toot in the current toot batch ([-1] means the last element of a list)
    last_earliest_id = threadToots[-1]["id"]

    # Calculate certain tootId range to request to the server
    tootOffsetPerBatch = int(last_earliest_id / maxBatches)

    # Prepare structures for parallel requesting
    threadArgs = []
    for batch in range(maxBatches):
        #               login info            maxId                                       minId
        threadArgs += [(app_data, last_earliest_id-batch*tootOffsetPerBatch, last_earliest_id-(batch+1)*tootOffsetPerBatch)]

    # Launch multiple threads to request toots concurrently
    import multiprocessing as mpd
    with mpd.Pool(processes=mpd.cpu_count()-1) as pool:
        threadToots = pool.starmap(fetchTimeline, threadArgs)

    # Merge toot batches into a single list
    toots = []
    for threadToot in threadToots:
        toots += threadToot

    # Return fetched toot list
    return toots

######################################## Main function #################################################################


def main():
    global spamTermsToFilter

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
        with open(app_data_json, "w") as file:
            json.dump(app_data, file, indent=4)

    # The current app/bot is registered at this point
    # Now to the login and access token generation

    if not os.path.exists(app_data["name"]+"_usercred.secret"):
        mastodonInstance = Mastodon(client_id=app_data["name"]+"_clientcred.secret",
                            api_base_url=app_data["base_url"]
                            )

        mastodonInstance.log_in(app_data["username"],
                        app_data["password"],
                        to_file=app_data["name"]+"_usercred.secret"
                        )

    # At this point, the login was done and the access token is available for use
    # Now to the toot fetching

    mastodonInstance = Mastodon(client_id=app_data["username"],
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

    # Fetch toots in parallel
    #toots_window = fetchToots(100, mastodonInstance, app_data)

    # Store the earliest toot in the current toot batch ([-1] means the last element of a list)
    last_earliest_id = mastodonInstance.timeline_local()[-1]["id"]

    # Fetch toots sequentially
    toots_window = fetchTimeline(app_data=app_data, maxId=last_earliest_id, maxToots=1000, mastodonInstance=mastodonInstance)

    # Print number of fetched toots
    print(len(toots_window), "toots were fetched.")

    # Prepare dictionary to hold spammer user registries and list for toot statistics
    punishableUsers = {}
    individualTootsStatistics = []

    # Process each toot
    for toot in toots_window:
        # Verify if the toot is a spam (only for text)
        spam, detectedSpamTerm = checkIfTootIsSpam(toot["content"])

        # If the toot is spam
        if spam:
            # Get the ID of the user
            spammerId = toot["account"]["id"]

            # Add the new infringing toot
            if spammerId not in punishableUsers:
                punishableUsers[spammerId] = []
            punishableUsers[spammerId] += [punishableSpammer(toot, detectedSpamTerm)]

        # Collect word information for analysis
        individualTootsStatistics += [collectTootMetrics(toot)]

    # Apply the punishment selected in the beginning of the current file
    punishSpammers(punishment, punishableUsers, mastodonInstance)
    
    # Assemble and print the rank of most frequent words on the analyzed toots (may help find spam)
    word_rank = assembleMetricResults(individualTootsStatistics)

    for count in list(sorted(word_rank.keys(), reverse=True)):
        print(count, "appearences of words:", word_rank[count])

    # Dump word frequency
    with open("frequent_words.json", "w") as file:
        json.dump(word_rank, file, indent=4)

    # Dump recently punished spammers
    if len(punishableUsers) > 0:
        now = time.localtime(time.time())
        punishableUsersJson = "%d_%d_%d-punished_users.json" % (now.tm_year, now.tm_mon, now.tm_mday)
        with open(punishableUsersJson, "w") as file:
            file.write(json.dumps(punishableUsers, indent=4))

    # Fetch all spamTerms detected
    detectedSpamTerms = []
    for punishedUser in punishableUsers.values():
        for toot in punishedUser:
            detectedSpamTerms += [toot["spamTerm"]]

    # Print number of muted/silenced users and related spam terms that triggered their silencing/muting
    print("%d spammers were %s. Detected spam terms were: %s" % (len(punishableUsers), punishment, ", ".join(detectedSpamTerms)))

    # End graciously
    return

# Execute the main function
if __name__ == '__main__':
    main()
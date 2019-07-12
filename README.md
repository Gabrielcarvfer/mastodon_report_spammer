This script is intended for mastodon instances admins and moderators to automatically report posts that contain specific words, mainly targetting spammers. Automatically silencing and banning is still not an option as the moderation API is not available (https://github.com/tootsuite/mastodon/issues/8580).


How to use?
---------------------

First install python.
Then install the mastodon API library for python (pip install -r pip_requirements.txt or pip install Mastodon.py beautifulsoup4).
Then copy app_data_example.json to app_data.json and fill in the fields.
After that, put all spam terms that you want to filter on spamTermsToFilter.txt. 
They will be matched exactly as written.
Finally, choose the punishment for spammers on the main.py file (change the variable "action" with the value you want).. 
I recommend trying with "ignore" before setting to "report". 
Run "python3 main.py" and wait.

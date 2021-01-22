import tweepy
import logging
import datetime
import time
from pytz import timezone
from dateutil.tz import tzlocal
from random import randint

from change_unc import translate_string

KEYS_FILE='keys.txt'
MISC_FILE='misc.cfg'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Dict that stores misc config
misc_dict = {"REPLY_ID":'1','USED_UNICODE':'f'}

# Convert timezone from time object if necessary
def get_converted_timezone(time):
    localtz = tzlocal()
    westTz = timezone("Brazil/West")
    eastTz = timezone("Brazil/East")
    today = datetime.datetime.today()
    # No reason to format time if we are already at UTC -04
    if(localtz.utcoffset(today) != westTz.utcoffset(today)):
        localized = eastTz.localize(time)
        time = localized.astimezone(westTz)
    return time

def read_keys_file(file):
    dct = {'CONS_KEY':'', 'CONS_SECRET':'', 'ACC_TOKEN':'', 'ACC_SECRET':''}
    with open(file,'r') as key_f:
        for line in key_f:
            tp,key = line.strip('\n').split('=')
            # Check for key file integrity
            if tp not in dct:
                raise("Invalid keys file")
            dct[tp] = key

    for tp in dct:
        if dct[tp] == '':
            raise("Missing key {} in key file".format(tp))
    return dct

def read_misc_file():
    with open(MISC_FILE,'r') as misc_f:
        for line in misc_f:
            tp, key = line.strip('\n').split('=')
            if tp not in misc_dict:
                raise("Invalid misc file")
            misc_dict[tp] = key

    for tp in misc_dict:
        if misc_dict[tp] == '':
            raise("Missing config {} in misc file".format(tp))

def write_misc_file():
    misc_f = open(MISC_FILE,'w')
    try:
        for tp in misc_dict: 
            misc_f.write("{}={}\n".format(tp,misc_dict[tp]))
        misc_f.close()
    except KeyboardInterrupt:
        logger.info("Caught keyboard interrupt. Rewriting file and exiting...")
        misc_f.close()
        misc_f = open(MISC_FILE,'w')
        for tp in misc_dict: 
            misc_f.write("{}={}\n".format(tp,misc_dict[tp]))
        misc_f.close()
        exit(1)

def create_api():
    dct = read_keys_file(KEYS_FILE)
    # Auth to twitter
    auth = tweepy.OAuthHandler(dct['CONS_KEY'],dct['CONS_SECRET'])
    auth.set_access_token(dct['ACC_TOKEN'],dct['ACC_SECRET'])
    api = tweepy.API(auth)
    return api

def get_message(time):
    time = get_converted_timezone(time)
    if  3 <= time.hour < 13:
        prefix = "bom dia"
    elif 13 <= time.hour < 18:
        prefix = "boa tarde"
    else: 
        prefix = "boa noite"
    return "Samuel CO, {}!".format(prefix)

def tweet_message(api):
    current_time = datetime.datetime.now()
    tweet = get_message(current_time)
    # The last tweet did not use modified unicode characters
    if(misc_dict["USED_UNICODE"] == 'f'):
        # Translate message to similar unicode to circumvent twitter repetition rules
        tweet = translate_string(tweet)
        misc_dict["USED_UNICODE"] = 't'
        write_misc_file()
    else:
        # 1 in 5 chance to tweet without unicode changes
        if(randint(0,9)):
            tweet = translate_string(tweet)
        else:
            misc_dict["USED_UNICODE"] = 'f'
            write_misc_file()

    logger.info("Sending tweet at {}".format(current_time))
    api.update_status(tweet)
    return

#def update_sinceid(api):
#    logger.info("Updating since_id to avoid missing mentions.")
#    since_id=int(misc_dict["REPLY_ID"])
#    for tweet in tweepy.Cursos(api.mentions_timeline, since_id=since_id).items():


def check_mentions(api, since_id):
    logger.info("Retrieving mentions")
    new_since_id = since_id
    # Retrieve all tweets since since_id
    for tweet in tweepy.Cursor(api.mentions_timeline, since_id=since_id).items():
        new_since_id = max(tweet.id, new_since_id)
        # Template to reply
        template = "@{} {}"
        # Get time to reply
        current_time = datetime.datetime.now()
        # Get message
        message = get_message(current_time)
        # Build tweet
        twt = template.format(tweet.user.screen_name,message)
        # Log info
        logger.info(f"Answering to {tweet.user.name} at {current_time}")
        # Reply to user
        try:
            api.update_status(
                    status=twt,
                    in_reply_to_status_id=tweet.id,
                    )
        except tweepy.error.TweepError:
            logger.info("Trying to reply to already replied mention."
                        " Ignoring it!")
            return new_since_id

    return new_since_id 

# Go to the beggining of a minute
def go_to_beginning_minute():
    now = datetime.datetime.now()
    # Start at the beggining of a new minute
    to_zero = (60-now.second)%60
    if to_zero:
        future = now + datetime.timedelta(seconds=to_zero)
        time.sleep((future-now).total_seconds())

# If no new_id is sent, read id. Else, write new id
def save_access_id(new_id):
    misc_dict["REPLY_ID"] = new_id
    write_misc_file()
    
def main():
    api = create_api()
    read_misc_file()
    since_id = int(misc_dict["REPLY_ID"])
    logger.info("Starting bot...")
    # Core loop
    while True:
        logger.info("Sleeping until next minute...")
        # Sleep until next minute begins
        go_to_beginning_minute()

        now = datetime.datetime.now()
        # Tweet every 30 minutes
        if(now.minute%30):
            tweet_message(api)
        # Check and answer new mentions
        since_id = check_mentions(api, since_id)
        # Write back id into file, to avoid replying to the same tweets
        save_access_id(since_id)

if __name__ == "__main__":
    main()

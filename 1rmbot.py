#1RMBot - Chris McCall
import twitter
import re
import sqlite3 as lite
import sys
import time

con = None

regex = re.compile('(\d+)\s*x\s*(\d+)', flags=re.IGNORECASE)

def insertLastMention(connection, is_dm, id):
    if id is None:
        return False

    if connection is None:
        return False

    if is_dm:
        table = "LastDMLookupIds"
    else:
        table = "LastMentionLookupIds"

    ids = (id, lite.TimestampFromTicks(time.time()) )

    cur = connection.cursor()
    try:
        cur.execute("INSERT INTO " + table + "(TwitterId,  DateTime) VALUES(?, ?)", ids)
        #print "inserted into %s: %s" % (table, ids.__str__())
        con.commit()
        cur.close()
    except lite.Error, e:
        print "DB Error: %s" % e.args[0]
        return False

    return True

def lookupLastMention(connection, is_dm):
    if connection is None:
        return ""
    if is_dm is None:
        return ""

    if is_dm:
        table = "LastDMLookupIds"
    else:
        table = "LastMentionLookupIds"

    try:
        cur = connection.cursor()
        sql = "SELECT TwitterId FROM " + table + " ORDER BY Id DESC LIMIT 1"
        cur.execute(sql)
        row = cur.fetchone()
        if row is not None:
            print "Found oldest %s id of: %s" % (table, row[0])
            return row[0]
    except lite.Error, e:
        print "DB Error: %s" % e.args[0]
        return ""
    finally:
        cur.close()

    return ""

def recordHistory (connection, user, is_dm, weight, inbound_id):
    if inbound_id is None:
        return False

    if connection is None:
        return False

    history = (user, weight["weight"], weight["reps"],inbound_id, is_dm, lite.TimestampFromTicks(time.time()) )
    #print "Committing history: " + history.__str__()

    cur = connection.cursor()
    try:
        cur.execute("INSERT INTO History(Username, Weight, Reps, TwitterId, IsDM, DateTime) VALUES(?, ?, ?, ?, ?, ?)", history)
        con.commit()
        cur.close()
    except lite.Error, e:
        print "DB Error: %s" % e.args[0]
        return False

    return True

def doLookUp(connection, id):
    if id is None:
        return True

    if connection is None:
        return True

    cur = connection.cursor()
    try:
        cur.execute("SELECT DateTime FROM History WHERE TwitterId=:Id", {"Id": id})
        con.commit()
        row = cur.fetchone()
        cur.close()
        if row is not None:
            print "id %d was previously messaged at %s" % (id, row[0])
            return True
    except lite.Error, e:
        print "DB Error: %s" % e.args[0]
        return True

    return False

def parse_weights(in_text):
    print "parsing: " + in_text
    parsed = regex.search(in_text)
    if parsed is None:
        return None
    weight = parsed.group(1)
    if weight is None:
        return None
    reps = parsed.group(2)
    if reps is None:
        return None

    return dict([('weight', weight), ('reps', reps)])

def get_max(weights):
    if weights is None:
        return None
    reps = float(weights['reps'])
    weight = float(weights['weight'])

    if reps > 10 or reps < 1:
        print 'rep range invalid'
        return None

    if weight < 0 or weight > 1000:
        print 'weight range invalid'
        return None

    # print 'weights and reps are valid'
    max = 0
    if reps == 10:
        max = round(weight / 0.75)
        #Math.round(form.WeightLifted.value/0.75)
    else:
        max = round(weight / (1.0278 - (0.0278 * reps)))
        # Math.round(form.WeightLifted.value/(1.0278-0.0278*form.RepsPerformed.value))
    max = max.__int__()
    return max

def do_1rm_dm(sender_id, screen_name, max, api):
    if max is None:
        return False

    if screen_name is None:
        return False

    if sender_id is None:
        return False

    msg = max.__str__() + " lbs"
    print "## DMing " + screen_name.__str__() + " " + msg.__str__()
    api.PostDirectMessage(screen_name, msg)
    return True

def do_1rm_tweet(user, status_id, max, api):
    if max is None:
        return False

    if user is None:
        return False

    if status_id is None:
        return False

    if api is None:
        return False

    tweet = "@" + user.GetScreenName() + " " + max.__str__() + " lbs"
    print tweet
    api.PostUpdate(tweet, status_id)
    return True

api = twitter.Api(consumer_key='x',
                  consumer_secret='x',
                  access_token_key='x',
                  access_token_secret='x')

try:
    con = lite.connect('1rmbot.db')
#    cur = con.cursor()
#    cur.execute("DROP TABLE IF EXISTS History")
#    cur.execute("CREATE TABLE History(Id INTEGER PRIMARY KEY, Username TEXT, Weight INT, Reps INT, TwitterId INT, IsDM BOOLEAN, DateTime TEXT);")
#    cur.execute("DROP TABLE IF EXISTS LastDMLookupIds")
#    cur.execute("CREATE TABLE LastDMLookupIds(Id INTEGER PRIMARY KEY, TwitterId INT, DateTime TEXT);")
#    cur.execute("DROP TABLE IF EXISTS LastMentionLookupIds")
#    cur.execute("CREATE TABLE LastMentionLookupIds(Id INTEGER PRIMARY KEY, TwitterId INT, DateTime TEXT);")
#    cur.close()

except lite.Error, e:
    print "DB Error: %s" % e.args[0]
    #cur.close()
    con.close()
    sys.exit(1)

mention_since_id = lookupLastMention(con, False)
dm_since_id = lookupLastMention(con, True)

previous_mention_since_id = mention_since_id
previous_dm_since_id = dm_since_id

while True:
    print "===========attempting lookups==========="
    #print "mention since id: " + mention_since_id.__str__()
    mentions = api.GetMentions(mention_since_id)

    for m in mentions:
        mention_since_id = m.GetId()
        weights = parse_weights(m.text)
        if (weights is not None) and (doLookUp(con, m.GetId() ) is False):
            if do_1rm_tweet(m.GetUser(), m.GetId(), get_max(weights), api):
                recordHistory(con, m.GetUser().GetScreenName(), False, weights, m.GetId())


    #print "dm since id: " + dm_since_id.__str__()
    dms = api.GetDirectMessages(dm_since_id)

    for dm in dms:
        dm_since_id = dm.GetId()
        weights = parse_weights(dm.text)
        if (weights is not None) and (doLookUp(con, dm.GetId()) is False):
            if do_1rm_dm(dm.GetSenderId(), dm.GetSenderScreenName(), get_max(weights), api):
                recordHistory(con, dm.GetSenderScreenName(), True, weights, dm.GetId())

    if previous_mention_since_id != mention_since_id:
        insertLastMention(con, False, mention_since_id)
        previous_mention_since_id = mention_since_id

    if previous_dm_since_id != dm_since_id:
        insertLastMention(con, True, dm_since_id)
        previous_dm_since_id = dm_since_id

    time.sleep(15)

if con:
    con.close()
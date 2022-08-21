import time

from flask import Flask, request, redirect, render_template
import sqlite3
from redis import Redis
import random
import json
from validators import url

app = Flask(__name__)

HOUR = 3600
SHORTEN_CHARS = list("qwertzuiopasdfghjklyxcvbnmQWERTZUIOPASDFGHJKLYXCVBNM1234567890")
SHORTEN_LENGTH = 6

random.seed(time.time())


def create_shorten():
    return "".join(random.choices(SHORTEN_CHARS, k=SHORTEN_LENGTH))

# !!!
# SHORTEN = the id that is paired with the shortened url
# POINTS =  the url that user is going to be redirected when passed then SHORTEN


class Database:
    def __init__(self):
        self.conn = sqlite3.connect("data.db", check_same_thread=False)
        self.c = self.conn.cursor()
        self.c.execute("CREATE TABLE if not exists 'shortens' (points	TEXT NOT NULL,shorten	TEXT NOT NULL);")
        self.conn.commit()
        self.rds = Redis()

    def cache(self, key_name, cache_data, expire_seconds):
        if self.rds.get(key_name) is not None:
            raise Warning(f"key {key_name} already exists! skipping")
        else:
            self.rds.setex(key_name, expire_seconds, cache_data)

    def get_pointed(self, uid):
        cache_hit = self.rds.get(f"shortid:{uid}")
        if not cache_hit:
            self.c.execute("SELECT points FROM shortens WHERE shorten=:uid", {"uid": uid})
            ftch = self.c.fetchone()
            if ftch:
                return ftch[0], False
            else:
                return None, False
        else:
            return json.loads(cache_hit).get("points"), True

    def shorten_exists(self, uid):
        cache_hit = self.rds.get(f"shortid:{uid}")
        if not cache_hit:
            self.c.execute("SELECT points FROM shortens WHERE shorten=:uid", {"uid": uid})
            ftch = self.c.fetchone()
            if ftch:
                return True
            else:
                return False
        else:
            return True

    def create_nonexistent_shorten(self):
        shorten = create_shorten()
        while self.shorten_exists(shorten):
            shorten = create_shorten()
        return shorten

    def add(self, data):
        recreate = {
            "points": data.get("target"),
            "shorten": self.create_nonexistent_shorten()
        }
        if recreate.get("points") is None:
            return {"status": "ERROR", "message": "There was no url provided to shorten"}
        if not url(recreate.get("points")):
            return {"status": "ERROR", "message": "Url you provided is not an valid url"}
        # caching shorten into memory for an hour
        self.cache(f"shortid:{recreate.get('shorten')}", json.dumps(recreate), HOUR)
        self.c.execute("INSERT INTO shortens VALUES (:p, :s)",
                       {"p": recreate.get("points"), "s": recreate.get("shorten")})
        self.conn.commit()
        return {"status": "SUCCESS", "new_url_id": recreate.get("shorten"),
                "message": "Your redirect was created successfully"}


db = Database()


@app.route("/<shorten_id>", methods=["GET"])
def redirect_shoreten(shorten_id):
    red, cachehit = db.get_pointed(shorten_id)
    if not cachehit and red is not None:
        # caching when someone accesses
        db.cache(f"shortid:{shorten_id}", json.dumps({"points": red, "shorten": shorten_id}), HOUR)
    if red is not None:
        # redirect
        return redirect(red), 200
    else:
        # Redirect not found
        return render_template("not_found.html"), 404


@app.route("/create", methods=["POST"])
def create():
    # create shorten
    data = request.get_json()
    return db.add(data)


if __name__ == "__main__":
    app.run(debug=True)

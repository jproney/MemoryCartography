"""
Toss some packets at the nginx server
"""

import urllib2
import random
import string

def send(hostname, port, un, pw):

    # Some of these are probably unnecessary, but whatever
    headers = {
        "Host" : "{}".format(hostname),
        "Connection" : "keep-alive",
        "sec-ch-ua":  '"Google Chrome";v="87", " Not;A Brand";v="99", "Chromium";v="87"',
        "sec-ch-ua-mobile" : "?0",
        "Upgrade-Insecure-Requests" : "1",
        "User-Agent" : "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36",
        "Accept" : "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Sec-Fetch-Site" : "same-origin",
        "Sec-Fetch-Mode" : "navigate",
        "Sec-Fetch-User" : "?1",
        "Sec-Fetch-Dest" : "document",
        "Referer" : "https://{}/index.html?username={}&password={}".format(hostname, un, pw),
        "Accept-Encoding" : "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie" : "heartbleed",
    }


    url = 'https://{}:{}/index.html?username={}&password={}'.format(hostname, port, un, pw)
    req = urllib2.Request(url)
    for k in headers.keys():
        req.add_header(k, headers[k])


    return urllib2.urlopen(req) 

if __name__ == "__main__":
    host = "192.168.26.2"
    port = 443

    num_reqs = random.randrange(5,21)
    print num_reqs
    for i in range(num_reqs):
        un = "creativename{}_".format(i) + ''.join(random.choice(string.ascii_uppercase) for _ in range(16))
        pw = "strongpassword{}_".format(i) + ''.join(random.choice(string.ascii_uppercase) for _ in range(16))
        send(host, port, un, pw)

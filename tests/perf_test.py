#encoding: utf-8
import os
import sys
import time
import json
import pprint
import random
import datetime
import subprocess
import collections
from optparse import OptionParser
from multiprocessing.dummy import Pool as ThreadPool

sys.path.append('../lib')
import tools

CONFIG_PATH = '/usr/local/etc/test.conf'
settings = tools.Configuration(CONFIG_PATH).get_section('perf_test')

class TestLog(object):
    def __init__(self, verbose=False):
        self.test_log = []
        self.verbose = verbose

    def write(self, message, level='info'):
        time = datetime.datetime.now().strftime('[%Y-%m-%d %H:%M:%S] ')
        msg = time + message
        if self.verbose:
            print message
        self.test_log.append({'message': message, 'level': level})

class Facter(object):
    abc = u'a b c d e f g h i g k l m n o p q r s t u v w x y z 1 2 3 4 5 6 7 8 9 0'.split()

    @property
    def word(self):
        word_len = random.randint(2, 10)
        return ''.join(random.sample(self.abc, word_len))
    
    def get_new_sentance(self, minl, maxl):
        return ' '.join([self.word for w in range(random.randint(minl, maxl))])

    @property
    def name(self):
        return self.get_new_sentance(1, 4)

    @property
    def message(self):
        return self.get_new_sentance(20, 30)

    @property
    def email(self):
        domens = ['mail.ru', 'gmail.com', 'list.ru', 'yahoo.com', 'ua.ru', 'ya.ru', 'bk.ru']
        return '%s@%s' % (self.word, random.choice(domens))

    @property
    def date(self):
        d = datetime.datetime(2013, random.randint(1, 12), random.randint(1, 27), random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))
        return d.strftime('%Y-%m-%d %H:%M:%S')

    @property
    def bool(self):
        return random.choice([True, False])

    @property
    def order(self):
        return random.choice(['asc', 'desc'])

    @property
    def limit(self):
        return random.randint(10, 100)

    def get_entity(self, etype):
        k = etype + 's'
        return random.choice(getattr(state, k))


class APIRequest(object):
    def __init__(self, ip):
        self.url_prefix = settings['url'].replace('ip', ip)
        self.errors = 0

    def execute(self, location, query_dict, post=False):
        url = self.url_prefix + location
        try:
            log.write('Requesting %s with %s (POST=%s)' % (url, str(query_dict), post))
            start = time.time()
            response = tools.Request(url, query_dict, post).get_response()
            req_time = time.time() - start
            log.write('Request time was: %.4f sec' % req_time)
            return response
        except ValueError, e:
            log.write('Request error: %s' % str(e), level='error')
            self.errors += 1
            if self.errors > 100:
                log.write('Exiting: %s API errors' % self.errors, level='error')
                raise ValueError("Too many errors!")
    
    def request(self, location, query_dict, post=False):
        url = self.url_prefix + location
        if not post:
            return tools.Request(url, query_dict, post).prepared_url, None
        else:
            return tools.Request(url, query_dict, post).prepared_url, json.dumps(query_dict)


class ForumEntity(object):

    def __str__(self):
        return pprint.pformat(self.__dict__)

    @property
    def type(self):
        return self.__class__.__name__.lower()

    @property
    def unique_id(self):
        id_attr_for_type = {
            'forum': 'short_name',
            'thread': 'id',
            'post': 'id',
            'user': 'email',
        }
        cls = self.type
        id_attr = id_attr_for_type[cls]
        return getattr(self, id_attr)

    @property
    def params(self):
        return self.__dict__

    def action(self, method, add_params=None, related=None):
        params = {
            self.type: facter.get_entity(self.type),
        }
        if add_params:
            params.update(add_params)
        if related:
            sample_related = random.sample(related, random.randint(0, len(related)))
            if sample_related:
                params['related'] = sample_related
        location = '/%s/%s/' % (self.type, method)
        post = True
        if method == 'details' or method.startswith('list'):
            post = False
        # return api.request(location=location, query_dict=params, post=post)
        return api.request(location=location, query_dict=params, post=post)

    def list(self, method, add_params=None, related=None):
        params = {
            'order': facter.order,
            'limit': facter.limit,
        }
        if add_params:
            params.update(add_params)
        return self.action(method=method, add_params=params, related=related)


class Forum(ForumEntity):
    def create(self, fill=False):
        params = {
            'name': facter.name,
            'short_name': facter.word,
        }
        location = '/%s/create/' % self.type
        params['user'] = random.choice(state.users)
        if fill:
            response = api.execute(location=location, query_dict=params, post=True)
            state.add_forum(response)
        else:
            return api.request(location=location, query_dict=params, post=True)

    def details(self):
        return super(Forum, self).action(method='details', related=['user'])
    
    def listPosts(self):
        return super(Forum, self).list(method='listPosts', related=['user', 'thread', 'forum'])

    def listThreads(self):
        return super(Forum, self).list(method='listThreads', related=['user', 'forum'])

    def listUsers(self):
        return super(Forum, self).list(method='listUsers', related=['user', 'forum'])


class Thread(ForumEntity):
    def create(self, fill=False):
        params = {
            'title' : facter.name,
            'slug' : facter.word,
            'date' : facter.date,
            'message' : facter.message,
            'isClosed' : facter.bool,
            'isDeleted' : facter.bool,
        }
        params['forum'] = random.choice(state.forums)
        params['user'] = random.choice(state.users)
        
        location = '/%s/create/' % self.type
        if fill:
            response = api.execute(location=location, query_dict=params, post=True)
            state.add_thread(response)
            state.forum_for_thread[response['id']] = params['forum']
        else:
            return api.request(location=location, query_dict=params, post=True)

    def details(self):
        return super(Thread, self).action(method='details', related=['user', 'forum'])

    def remove(self):
        return super(Thread, self).action(method='remove')

    def restore(self):
        return super(Thread, self).action(method='restore')

    def close(self):
        return super(Thread, self).action(method='close')

    def open(self):
        return super(Thread, self).action(method='open')

    def list(self):
        if not random.choice([0, 1]):
            entity = Forum()
        else:
            entity = User()
        params = {
            entity.type: facter.get_entity(entity.type),
        }
        return super(Thread, self).list(method='list', add_params=params)

    def listPosts(self):
        return super(Thread, self).list(method='listPosts')

    def update(self):
        params = {
            'message': facter.message,
            'slug': facter.word,
        }
        return super(Thread, self).action(method='update', add_params=params)

    def vote(self):
        params = {
            'vote': random.choice([1, -1]),
        }
        return super(Thread, self).action(method='vote', add_params=params)

    def subscribe(self):
        params = {
            'user': random.choice(state.users),
        }
        return super(Thread, self).action(method='subscribe', add_params=params)

    def unsubscribe(self):
        params = {
            'user': random.choice(state.users),
        }
        return super(Thread, self).action(method='unsubscribe', add_params=params)


class Post(ForumEntity):
    def create(self, fill=False):
        params = {
            # 'message' : facter.message,
            'isApproved' : facter.bool,
            'isSpam' : facter.bool,
            'isDeleted' : facter.bool,
            'isEdited' : facter.bool,
            'isHighlighted' : facter.bool,
            'date' : facter.date,
        }
        location = '/%s/create/' % self.type
        params['message'] = ' '.join([facter.message for i in range(30)])
        params['thread'] = random.choice(state.threads)
        params['user'] = random.choice(state.users)
        params['forum'] = state.forum_for_thread[params['thread']]

        is_new = True if not random.randint(0, 2) else False
        avaliable_parents = state.posts_for_thread[params['thread']]
        if is_new or not avaliable_parents:
            params['parent'] = None
        else:
            params['parent'] = random.choice(avaliable_parents)
        if fill:
            response = api.execute(location=location, query_dict=params, post=True)
            state.add_post(response)
            state.posts_for_thread[params['thread']].append(response['id'])
        else:
            return api.request(location=location, query_dict=params, post=True)

    def details(self):
        return super(Post, self).action(method='details', related=['user', 'thread', 'forum'])

    def list(self):
        if not random.choice([0, 1]):
            entity = Forum()
        else:
            entity = Thread()
        params = {
            entity.type: facter.get_entity(entity.type),
        }
        return super(Post, self).list(method='list', add_params=params)

    def remove(self):
        return super(Post, self).action(method='remove')

    def restore(self):
        return super(Post, self).action(method='restore')

    def update(self):
        params = {
            'message': facter.message,
        }
        return super(Post, self).action(method='update', add_params=params)

    def vote(self):
        params = {
            'vote': random.choice([1, -1]),
        }
        return super(Post, self).action(method='vote', add_params=params)


class User(ForumEntity):
    def create(self, fill=False):
        params = {}
        if not random.randint(0, 2):
            params = {
                'name': None,
                'username': None,
                'about': None,
                'isAnonymous': True,
                'email': facter.email,
            }
        else:
            params = {
                'name': facter.name,
                'username': facter.word,
                'about': facter.message,
                'isAnonymous': False,
                'email': facter.email,
            }
        location = '/%s/create/' % self.type
        if fill:
            response = api.execute(location=location, query_dict=params, post=True)
            state.add_user(params)
        else:
            return api.request(location=location, query_dict=params, post=True)

    def details(self):
        return super(User, self).action(method='details')

    def follow(self):
        params = {
            'follower': random.choice(state.users),
            'followee': random.choice(state.users),
        }
        return super(User, self).action(method='follow', add_params=params)
    
    def unfollow(self):
        params = {
            'follower': random.choice(state.users),
            'followee': random.choice(state.users),
        }
        return super(User, self).action(method='unfollow', add_params=params)

    def listFollowers(self):
        return super(User, self).list(method='listFollowers')

    def listFollowing(self):
        return super(User, self).list(method='listFollowing')

    def listPosts(self):
        return super(User, self).list(method='listPosts')

    def updateProfile(self):
        params = {
            'about': facter.message,
            'name': facter.name,
        }
        return super(User, self).action(method='listPosts',  add_params=params)

class State(object):
    def __init__(self):
        self.entities = {
                'users': [],
                'forums': [],
                'threads': [],
                'posts': [],
            }
        self.forum_for_thread = {}
        self.posts_for_thread = collections.defaultdict(list)

    @property
    def users(self):
        return self.entities['users']
    @property
    def forums(self):
        return self.entities['forums']
    @property
    def threads(self):
        return self.entities['threads']
    @property
    def posts(self):
        return self.entities['posts']

    def add_user(self, u):
        self.users.append(u['email'])

    def add_forum(self, f):
        self.forums.append(f['short_name'])

    def add_thread(self, t):
        self.threads.append(t['id'])

    def add_post(self, p):
        self.posts.append(p['id'])


class Filler(object):
    @staticmethod
    def run():
        t = [
            ('users', User),
            ('forums', Forum),
            ('threads', Thread),
            ('posts', Post),
        ]

        for entity, factory_cls in t:
            entities = [True for i in range(int(settings[entity]))]
            factory = factory_cls().create
            pool = ThreadPool(int(settings['num_threads']))
            try:
                pool.map(factory, entities)
                pool.close()
                pool.join()
            except Exception, e:
                print e
                pool.terminate()
                sys.exit(1)
        
        a = [
            (int(settings['followers']), User().follow),
            (int(settings['subscribptions']), Thread().subscribe),
        ]
        for it, method in a:
            for i in range(it):
                    url, args = method()
                    print "Requesting %s with %s" % (url,  args)
                    try:
                        args = json.loads(args)
                        tools.Request(url, args, post=True).get_response()
                    except:
                        pass


class HTTPerfScenario(object):
    def __init__(self):
        self.locations = {
            'read': [
                User().details,
                User().listFollowing,
                User().listFollowers,
                User().listPosts,
                Post().list,
                Post().details,
                Thread().details,
                Thread().list,
                Thread().listPosts,
                Forum().details,
                Forum().listPosts,
                Forum().listThreads,
                Forum().listUsers,
            ],
            'write': [
                User().create,
                User().follow,
                User().unfollow,
                Post().create,
                Post().vote,
                Post().restore,
                Post().remove,
                Post().update,
                Thread().create,
                Thread().remove,
                Thread().restore,
                Thread().close,
                Thread().open,
                Thread().update,
                Thread().vote,
                Thread().subscribe,
                Thread().unsubscribe,
                Forum().create,
            ]
        }

    def run(self, name_prefix):
        writes_per_ses = int(settings['rps']) * int(settings['write']) / 100
        reads_per_ses = int(settings['rps']) * int(settings['read']) / 100
        reads_per_ses += int(settings['rps']) - writes_per_ses + reads_per_ses
        session = ['r' for i in xrange(reads_per_ses)] + ['w' for j in xrange(writes_per_ses)]
        with open(name_prefix + '_httperf_scenario', 'w') as fh:
            for s in xrange(int(settings['sessions'])):
                random.shuffle(session)
                if s != 0:
                    fh.write('\n')
                for i, request_type in enumerate(session):
                    if request_type == 'r':
                        loc = random.choice(self.locations['read'])
                    if request_type == 'w':
                        loc = random.choice(self.locations['write'])
                    url, query_args = loc()
                    if not url.strip(): print loc
                    url = 'db' + url.split('db')[-1]
                    if i != 0:
                        url = '\t' + url
                    if request_type == 'w':
                        url += " method=POST contents='%s'" % query_args
                    if url.strip() == 'db': continue
                    fh.write(url + '\n')


class Students(object):
    filepath = "students.json"
    def __init__(self, options):
        if options.local:
            self.data = {u'Я': {'slug': 'me', 'ip': options.ip_port, 'email': u's.stupnikov@corp.mail.ru', 'passed': True, 'filled_up': False}}
        else:            
            with open(self.filepath) as f:
                self.data = json.load(f)
    def save(self):
        if not options.local:
            with open(self.filepath, "w") as f:
                json.dump(self.data, f)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-l", "--local", dest="local",
                      action="store_true", default=False, help="run local")
    parser.add_option("-v", "--verbose", dest="verbose",
                      action="store_true", default=False, help="log to stdout")
    parser.add_option("-a", "--address", dest="ip_port",
                      action="store", type="string", default='127.0.0.1:5000')
    (options, args) = parser.parse_args()
    students = Students(options)
    for name, student in sorted(students.data.items(), key=lambda t: t[0]):
        if student['filled_up']:
            print "%s DB is already filled up" % name
            continue
        if not student['passed']:
            print "%s didnt passed the func test" % name
            continue
        name_utf = name.encode('utf-8')
        student['ip'] = student['ip'].encode('utf-8')
        student['email'] = student['email'].encode('utf-8')
        log = TestLog(options.verbose)
        state = State()
        facter = Facter()
        api = APIRequest(student['ip'])
        log.write('\n\t\tStarted for: %s\n' % student)
        api.execute('/clear/', {}, post=True)
        s = time.time()
        Filler.run()
        print 'FILLER: ' + str(time.time() - s)
        s = time.time()
        HTTPerfScenario().run(student['slug'])
        print 'SCENARIO: ' + str(time.time() - s)

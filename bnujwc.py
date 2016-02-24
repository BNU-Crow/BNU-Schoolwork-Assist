import requests
import re
import hashlib
import base64
from datetime import datetime
import xml.etree.cElementTree as etree
from html.parser import HTMLParser
import execjs
import random
import json


class LoginError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class TableHTMLParser(HTMLParser):
    def __init__(self):
        self.start_td = self.start_tr = False
        self.courses = []
        self.course = {}

        HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.start_tr = True
        elif tag == 'td' and self.start_tr:
            for k, v in attrs:
                if k == 'name':
                    self.start_td = v
                    break
                else:
                    self.start_td = False

    def handle_endtag(self, tag):
        if tag == 'tr':
            if len(self.course):
                self.courses.append(self.course)
                self.course = {}
            self.start_tr = False
        elif tag == 'td':
            self.start_td = False

    def handle_data(self, data):
        if self.start_td:
            self.course[self.start_td] = data


class BNUjwc:
    _login_url = 'http://cas.bnu.edu.cn/cas/login?service=http%3A%2F%2Fzyfw.bnu.edu.cn%2FMainFrm.html'
    _student_info_url = 'http://zyfw.bnu.edu.cn/STU_DynamicInitDataAction.do' \
                        '?classPath=com.kingosoft.service.jw.student.pyfa.CourseInfoService&xn=2015&xq_m=1'
    _table_url = 'http://zyfw.bnu.edu.cn/taglib/DataTable.jsp?tableId='
    _deskey_url = 'http://zyfw.bnu.edu.cn/custom/js/SetKingoEncypt.jsp?random='
    _cancel_course_url = 'http://zyfw.bnu.edu.cn/jw/common/cancelElectiveCourse.action'
    _select_elective_course_url = 'http://zyfw.bnu.edu.cn/jw/common/saveElectiveCourse.action'

    _course_list_table_id = '5327018'
    _cancel_list_table_id = '6093'
    _elective_course_list_table_id = '5327095'

    def __init__(self):
        self._s = requests.Session()
        self._s.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'http://zyfw.bnu.edu.cn'
        })

        self._lt = ''
        self._execution = ''
        self._info = {}
        self._parser = TableHTMLParser()

        # des js
        with open('des.js', 'r') as f:
            self._des = execjs.compile(f.read())

    def _get_login_params(self):
        """
        get lt and execution params for login
        :return: lt, execution
        """
        if self._lt and self._execution:
            return

        lt = ''
        execution = ''

        r = self._s.get(BNUjwc._login_url)

        if r.status_code != 200:
            raise LoginError('获取登录参数失败')

        html = r.text

        m = re.search(r'input type="hidden" name="lt" value="(.*)"', html)
        if m:
            lt = m.group(1)

        m = re.search(r'input type="hidden" name="execution" value="(.*)"', html)
        if m:
            execution = m.group(1)

        self._lt = lt
        self._execution = execution

    def _get_student_info(self):
        """
        get student information (grade, semester, student id ...
        :return:
        """
        if self._info:
            return

        r = self._s.post(BNUjwc._student_info_url)
        info_node = etree.fromstring(r.text)

        self._info[info_node[0].tag] = info_node[0].text
        for e in info_node[1]:
            self._info[e.tag] = e.text

    def _get_table_list(self, table_id, post_data):
        r = self._s.post(BNUjwc._table_url + table_id, data=post_data)
        self._parser.feed(r.text)
        return self._parser.courses

    def _encrypt_params(self, params):

        r = self._s.get(BNUjwc._deskey_url + str(random.randint(0, 10000000)))

        _deskey = ''
        m = re.search(r"var _deskey = '(.*)';", r.text)
        if m:
             _deskey = m.group(1)

        timestamp = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        m = hashlib.md5()
        m.update(params.encode('ascii'))
        params_md5 = m.hexdigest()
        m = hashlib.md5()
        m.update(timestamp.encode('ascii'))
        time_md5 = m.hexdigest()
        m = hashlib.md5()
        m.update((params_md5+time_md5).encode('ascii'))
        token = m.hexdigest()
        _params = base64.b64encode(self._des.call('strEnc', params, _deskey).encode())
        return _params, token, timestamp

    def login(self, username, password):
        """
        login with username and password
        :param username: username (student id)
        :param password: password (default: birthday - yyyymmdd)
        :return: None
        """
        self._get_login_params()

        post_data = {
            'username': username,
            'password': password,
            'code': 'code',
            'lt': self._lt,
            'execution': self._execution,
            '_eventId': 'submit'
        }

        try:
            r = self._s.post(BNUjwc._login_url, data=post_data)
        except ConnectionError as e:
            raise LoginError('连接失败：' + e.strerror)
        if r.text.find('用户名密码输入有误。') != -1:
            raise LoginError('用户密码错误')
        if r.status_code != 200:
            raise LoginError('登录提交失败！状态码：' + str(r.status_code))

    def get_plan_courses(self, show_full=False):
        self._get_student_info()
        post_data = {
            'initQry': 0,
            'xktype': 2,
            'xh': self._info['xh'],
            'xn': self._info['xn'],
            'xq': self._info['xq_m'],
            'nj': self._info['nj'],
            'zydm': self._info['zydm'],
            'items': '',
            'is_xjls': 'undefined',
            'kcfw': 'zxbnj',
            'njzy': self._info['nj'] + '|' + self._info['zydm'],
            'lbgl': '',
            'kcmc': '',
            'kkdw_range': 'all',
            'sel_cddwdm': '',
            'menucode_current': 'JW130403',
            'btnFilter': '类别过滤',
            'btnSubmit': '提交'
        }
        if not show_full:
            post_data['xwxmkc'] = 'on'
        return self._get_table_list(BNUjwc._course_list_table_id, post_data)

    def get_cancel_courses(self):
        self._get_student_info()
        post_data = {
            'xktype': 5,
            'xh': self._info['xh'],
            'xn': self._info['xn'],
            'xq': self._info['xq_m'],
            'nj': self._info['nj'],
            'zydm': self._info['zydm'],
            'items': '',
            'kcfw': 'All',
            'menucode_current': 'JW130406',
            'btnQry': '检索'
        }
        return self._get_table_list(BNUjwc._cancel_list_table_id, post_data)

    def get_elective_courses(self, show_full=False):
        self._get_student_info()
        post_data = {
            'initQry': 0,
            'xktype': 2,
            'xh': self._info['xh'],
            'xn': self._info['xn'],
            'xq': self._info['xq_m'],
            'nj': self._info['nj'],
            'zydm': self._info['zydm'],
            'kcdm': '',
            'kclb1': '',
            'kclb2': '',
            'khfs': '',
            'skbjdm': '',
            'skbzdm': '',
            'xf': '',
            'kcfw': 'zxggrx',
            'njzy': self._info['nj'] + '|' + self._info['zydm'],
            'items': '',
            'is_xjls': 'undefined',
            'kcmc': '',
            'menucode_current': 'JW130415'
        }
        if not show_full:
            post_data['xwxmkc'] = 'on'
        return self._get_table_list(BNUjwc._elective_course_list_table_id, post_data)

    def cancel_course(self, course):

        self._get_student_info()
        params = "xn=%s&xq=%s&xh=%s&kcdm=%s&skbjdm=%s&xktype=5" % (self._info['xn'], self._info['xq_m'],
                                                                   self._info['xh'], course['kcdm'], course['skbjdm'])
        _params, token, timestamp = self._encrypt_params(params)
        r = self._s.post(BNUjwc._cancel_course_url, data={
            'params': _params,
            'token': token,
            'timestamp': timestamp
        })
        return json.loads(r.text)

    def select_elective_course(self, course):
        self._get_student_info()
        params = "xktype=2&initQry=0&xh=%s&xn=%s&xq=%s&nj=%s&zydm=%s&" \
                 "kcdm=%s&kclb1=%s&kclb2=%s&khfs=%s&skbjdm=%s&" \
                 "skbzdm=&xf=%s&kcfw=zxggrx&njzy=%s&items=&is_xjls=undefined&" \
                 "kcmc=&t_skbh=&menucode_current=JW130415"\
                 % (self._info['xh'], self._info['xn'], self._info['xq_m'], self._info['nj'], self._info['zydm'],
                    course['kcdm'], course['kclb1'], course['kclb2'], course['khfs'], course['skbjdm'],
                    course['xf'], self._info['nj'] + '|' + self._info['zydm'])

        _params, token, timestamp = self._encrypt_params(params)
        r = self._s.post(BNUjwc._select_elective_course_url, data={
            'params': _params,
            'token': token,
            'timestamp': timestamp
        })
        return json.loads(r.text)

if __name__ == '__main__':
    jwc = BNUjwc()
    with open('user.txt', 'r') as f:
        jwc.login(f.readline().strip(), f.readline().strip())
    print(jwc._get_student_info())
    """
    courses = jwc.get_elective_courses()
    for i, course in enumerate(courses):
        print(i, course)
    i = input()
    print(jwc.select_elective_course(courses[int(i)]))
    """

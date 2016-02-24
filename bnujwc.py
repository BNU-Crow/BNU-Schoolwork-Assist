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

    def feed(self, data):
        self.start_td = self.start_tr = False
        self.courses = []
        self.course = {}
        HTMLParser.feed(self, data)

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
    _view_planned_course_table_id = '6142'

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
        with open('des.js', 'r', encoding='utf8') as f:
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
        :return: {
            'zydm': '', # code for profression
            'nj': '2014', # grade
            'xn': '2015', # school year
            'xh': '', # student id
            'zymc': '', # profession
            'xq_m': '1' # semester
        }
        """
        if self._info:
            return

        r = self._s.post(BNUjwc._student_info_url)
        info_node = etree.fromstring(r.text)

        self._info[info_node[0].tag] = info_node[0].text
        for e in info_node[1]:
            self._info[e.tag] = e.text

        return self._info

    def _get_table_list(self, table_id, post_data, get_data = ''):
        """
        get table page and parse the table HTML to a list of dict
        :param table_id: ID of table to get
        :param post_data: POST data
        :return: a list of dict (each dict is a row)
        """
        if get_data:
            r = self._s.post(BNUjwc._table_url + table_id + '&' + get_data, data=post_data)
        else:
            r = self._s.post(BNUjwc._table_url + table_id, data=post_data)
        self._parser.feed(r.text)
        return self._parser.courses

    def _encrypt_params(self, params):
        """
        encrypt params to be POST
        :param params: params to be encrypted
        :return: encrypted params
        """
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
        """
        get planned courses
        :param show_full: do show the courses at full
        :return: a list of dict [{
            'kcxz': '01', # unknown
            'xkfs': '学生网上选', # selection method
            'sksjdd': '1-16周 四[9-10] 八111(62)', # when and where
            'rkjs': '[00]xx', # teacher
            'kcdm': '', # code for course
            'zxs': '', # total lecture hours,
            'xk_status': '选中', # status of selection
            'skbjdm': '', # code for class of the course
            'xk_points': '0', # needed point to select the course (deprecated)
            'xf': '', # score of the course
            'kclb2': '', # classification code 2 of course
            'khfs': '', # unknown
            'lb': '学校平台/大学外语模块/必修', # classification
            'operation': '查看', # operation
            'kclb1': '', # classification code 1 of course
            'kc': '[00]xx', # course name
            'is_buy_book': '0', # do buy book (deprecated)
            'is_cx': '0' # is rehabilitation course
        }, ...]
        """
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
        """
        get courses which can be canceled
        :return: a list of dict [{ # courses not selected have only items with '!'
            'xkfs': '学生网上选', # selection method
            'sksjdd': '1-16周 四[9-10] 八111(62)', # when and where
            'rkjs': '[00]xx', # teacher
            'school_name': '本部', # school name
            'kcdm': '', # code for course !
            'zxs': '', # total lecture hours !
            'xk_status': '选中', # status of selection
            'skbjdm': '', # code for class of the course
            'xk_points': '0', # needed point to select the course (deprecated)
            'xf': '', # score of the course !
            'kclb2': '', # classification code 2 of course !
            'show_skbjdm': '', # code shown for class of course
            'khfs': '', # unknown !
            'lb': '学校平台/大学外语模块/必修', # classification !
            'operation': '退选', # operation !
            'kclb1': '', # classification code 1 of course !
            'kc': '[00]xx', # course name !
            'kcxz': '' # unknown !
        }, ...]
        """
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
        """
        get elective courses
        :param show_full: do show the courses at full
        :return: a list of dict [{
            'xkfs': '学生网上选', # selection method
            'sksj': '1-16周 四[9-10]', # when
            'rkjs': '[00]xx', # teacher
            'kcdm': '', # code for course
            'zxs': '', # total lecture hours,
            'xz': '已选中', # status of selection
            'skbjdm': '', # code for class of the course
            'xk_points': '0', # needed point to select the course (deprecated)
            'xf': '', # score of the course
            'kclb2': '', # classification code 2 of course
            'khfs': '', # unknown
            'lb': '学校平台/大学外语模块/必修', # classification
            'operation': '查看', # operation
            'kclb1': '', # classification code 1 of course
            'kc': '[00]xx', # course name
            'is_buy_book': '0', # do buy book (deprecated)
            'is_cx': '0', # is rehabilitation course
            'skfs': '理论', # teaching method
            'yxrs': 'current/listen free', # number of student selecting the course
            'skdd': '七107', # where
            'xxrs': '', # capacity
            'skbj': '01', # class
            'kxrs': '' # remaining amount
        }, ...]
        """
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
        """
        cancel specific course
        :param course: course info dict returned by get_cancel_courses
        :return: {
            'result': '',
            'status': '200|400',
            'message': ''
        }
        """
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
        """
        select specific elective course
        :param course: course info dict returned by get_elective_courses
        :return: {
            'result': '',
            'status': '200|400',
            'message': ''
        }
        """
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

    def view_plan_course(self, course):
        """
        view specific planned course's details
        :param course: course info dict returned by get_plan_courses
        :return: a list of dict [{
            'sksj': '1-16周 四[9-10]', # when
            'rkjs': '[00]xx', # teacher
            'current_skbjdm': '', # code for child class of the course
            'skbjdm': '', # code for class of the course
            'skfs_mc': '理论', # teaching method
            'xkrs': 'current/listen free', # number of student selecting the course
            'skdd': '七107', # where
            'xkrssx': '', # capacity
            'kxrs': '', # remaining amount
            'xqdm': '0', # code for campus
            'xqmc': '本部', # campus
            'skfs_m': '0' # teaching method code
        }, ...]
        """
        self._get_student_info()
        params = 'xn=%s&xq_m=%s&xh=%s&kcdm=%s&skbjdm=&xktype=2&kcfw=zxbnj' \
                 % (self._info['xn'], self._info['xq_m'], self._info['xh'], course['kcdm'])
        post_data = {
            'initQry': 0,
            'electiveCourseForm.xktype': 2,
            'electiveCourseForm.xh': self._info['xh'],
            'electiveCourseForm.xn': self._info['xn'],
            'electiveCourseForm.xq': self._info['xq_m'],
            'electiveCourseForm.nj': self._info['nj'],
            'electiveCourseForm.zydm': self._info['zydm'],
            'electiveCourseForm.kcdm': course['kcdm'],
            'electiveCourseForm.kclb1': course['kclb1'],
            'electiveCourseForm.kclb2': course['kclb2'],
            'electiveCourseForm.kclb3': '',
            'electiveCourseForm.khfs': course['khfs'],
            'electiveCourseForm.skbjdm': '',
            'electiveCourseForm.skbzdm': '',
            'electiveCourseForm.xf': course['xf'],
            'electiveCourseForm.is_checkTime': '1',
            'kknj': '',
            'kkzydm': '',
            'txt_skbjdm': '',
            'electiveCourseForm.xk_points': '0',
            'electiveCourseForm.is_buy_book': '',
            'electiveCourseForm.is_cx': '',
            'electiveCourseForm.is_yxtj': '',
            'menucode_current': 'JW130403'
        }
        return self._get_table_list(BNUjwc._view_planned_course_table_id, post_data, params)

    def select_plan_course(self, course, child_course):
        """
        select specific planned course
        :param course: course info dict returned by get_plan_courses
        :param child_course: child course info dict returned by view_plan_course
        :return: {
            'result': '',
            'status': '200|400',
            'message': ''
        }
        """
        self._get_student_info()
        params = "xktype=2&xn=%s&xq=%s&xh=%s&nj=%s&zydm=%s&kcdm=%s&kclb1=%s&kclb2=%s&kclb3=" \
                 "&khfs=%s&skbjdm=%s&skbzdm=&xf=%s&is_checkTime=1&kknj=&kkzydm=&txt_skbjdm=" \
                 "&xk_points=0&is_buy_book=0&is_cx=0&is_yxtj=1&menucode_current=JW130403&kcfw=zxbnj"\
                 % (self._info['xn'], self._info['xq_m'], self._info['xh'], self._info['nj'], self._info['zydm'],
                    course['kcdm'], course['kclb1'], course['kclb2'], course['khfs'], child_course['skbjdm'],
                    course['xf'])

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

    courses = jwc.get_plan_courses()
    for i, course in enumerate(courses):
        print(i, course)
    i = int(input())
    child_courses = jwc.view_plan_course(courses[i])

    for j, child_course in enumerate(child_courses):
        print(j, child_course)
    j = int(input())

    print(jwc.select_plan_course(courses[i], child_courses[j]))
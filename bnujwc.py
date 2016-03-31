import requests
import re
import hashlib
import urllib
import base64
from datetime import datetime
import xml.etree.cElementTree as etree
from html.parser import HTMLParser
import execjs
import random
import json
from PIL import Image
from multiprocessing import Process
import time


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


class ResultHTMLParser(HTMLParser):
    def __init__(self):
        self.start_table = self.start_thead = self.start_td = self.start_tr = False
        self.tables = []
        self.table = []
        self.tr = []
        self.data = ''
        self.noskip = False

        HTMLParser.__init__(self)

    def feed(self, data, noskip = False):
        self.start_table = self.start_thead = self.start_td = self.start_tr = False
        self.tables = []
        self.table = []
        self.tr = []
        self.data = ''
        self.noskip = noskip
        HTMLParser.feed(self, data)

    def handle_starttag(self, tag, attrs):
        if self.start_table:
            if tag == 'thead':
                self.start_thead = True
            elif tag == 'tr' and not self.start_thead:
                self.start_tr = True
            elif tag == 'td' and self.start_tr:
                self.start_td = True
        elif tag == 'table':
            self.start_table = True
        self.tag = tag

    def handle_endtag(self, tag):
        if tag == 'tr':
            if len(self.tr):
                self.table.append(self.tr)
                self.tr = []
            self.start_tr = False
        elif tag == 'td':
            if self.start_td and self.noskip or len(self.tr) or self.data.strip():
                self.tr.append(self.data.strip())
                self.data = ''
            self.start_td = False
        elif tag == 'table':
            if len(self.table):
                self.tables.append(self.table)
                self.table = []
            self.start_table = False
        elif tag == 'thead':
            self.start_thead = False

    def handle_data(self, data):
        if self.start_td:
            if not self.data.strip():
                self.data = data.strip()


class EvaluateHTMLParser(HTMLParser):
    def __init__(self):
        self.select = set()
        self.text = set()
        HTMLParser.__init__(self)

    def feed(self, data, noskip = False):
        HTMLParser.feed(self, data)

    def handle_starttag(self, tag, attrs):
        if tag == 'input' or tag == 'textarea':
            isRadio = False
            value = ''
            for k, v in attrs:
                if k == 'type' and v == 'radio':
                    isRadio = True
                elif k == 'value':
                    value = v
                elif k == 'tmbh':
                    self.text.add(v.strip())
            if isRadio:
                self.select.add(v.split('@')[1].strip())

    def handle_endtag(self, tag):
        pass

    def handle_data(self, data):
        pass


class BNUjwc:
    _validate_code_url = 'http://zyfw.bnu.edu.cn/cas/genValidateCode?dateTime='
    _login_old_url = 'http://zyfw.bnu.edu.cn/cas/logon.action'
    _login_url = 'http://cas.bnu.edu.cn/cas/login?service=http%3A%2F%2Fzyfw.bnu.edu.cn%2FMainFrm.html'
    _student_info_url = 'http://zyfw.bnu.edu.cn/STU_DynamicInitDataAction.do' \
                        '?classPath=com.kingosoft.service.jw.student.pyfa.CourseInfoService&xn=2015&xq_m=1'
    _table_url = 'http://zyfw.bnu.edu.cn/taglib/DataTable.jsp?tableId='
    _deskey_url = 'http://zyfw.bnu.edu.cn/custom/js/SetKingoEncypt.jsp?random='
    _cancel_course_url = 'http://zyfw.bnu.edu.cn/jw/common/cancelElectiveCourse.action'
    _select_elective_course_url = 'http://zyfw.bnu.edu.cn/jw/common/saveElectiveCourse.action'
    _selection_result_url = 'http://zyfw.bnu.edu.cn/student/wsxk.zxjg10139.jsp?menucode=JW130404&random='
    _droplist_url = 'http://zyfw.bnu.edu.cn/frame/droplist/getDropLists.action'
    _exam_score_url = 'http://zyfw.bnu.edu.cn/student/xscj.stuckcj_data.jsp'
    _evaluate_list_url = 'http://zyfw.bnu.edu.cn/jw/wspjZbpjWjdc/getPjlcInfo.action'
    _evaluate_form_url = 'http://zyfw.bnu.edu.cn/student/wspj_tjzbpj_wjdcb_pj.jsp?'
    _evaluate_save_url = 'http://zyfw.bnu.edu.cn/jw/wspjZbpjWjdc/save.action'

    _course_list_table_id = '5327018'
    _cancel_list_table_id = '6093'
    _elective_course_list_table_id = '5327095'
    _view_planned_course_table_id = '6142'
    _exam_arragement_table_id = '2538'
    _evaluate_course_list_table_id = '50058'

    _exam_drop_name = 'Ms_KSSW_FBXNXQKSLC'

    def __init__(self, username, password):
        """
        :param username: username (student id)
        :param password: password (default: birthday - yyyymmdd)
        """
        self._username = username
        self._password = password

        self._s = requests.Session()
        self._s.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'http://zyfw.bnu.edu.cn'
        })

        self._lt = ''
        self._execution = ''
        self._info = {}
        self._table_parser = TableHTMLParser()
        self._result_parser = ResultHTMLParser()
        self._evaluate_parser = EvaluateHTMLParser()

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

    def _get_validate_code(self):
        """
        """
        r = self._s.get(BNUjwc._validate_code_url + str(random.randint(0, 1000000)), stream=True)
        with open('code.jpg', 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)

        img = Image.open('code.jpg')
        return img

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
        self._table_parser.feed(r.text)
        return self._table_parser.courses

    def _encrypt_params(self, params):
        """
        encrypt params to be POST
        :param params: params to be encrypted
        :return: encrypted params
        """
        r = self._s.get(BNUjwc._deskey_url + str(random.randint(100000, 100000000)))

        _deskey = ''
        m = re.search(r"var _deskey = '(.*)';", r.text)
        if m:
             _deskey = m.group(1)

        #timestamp = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        timestamp = '2016-01-01 00:00:00'
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

    def _get_droplist(self, name):
        post_data = {
            'comboBoxName': name,
        }
        r = self._s.post(BNUjwc._droplist_url, post_data);
        return r.text

    def _login_old(self, code):
        """
        login for old login site
        : param code: validate code
        :return: None
        """
        m = hashlib.md5()
        m.update(self._password.encode())
        pwd = m.hexdigest()
        m = hashlib.md5()
        m.update(code.encode())
        pwd += m.hexdigest()
        m = hashlib.md5()
        m.update(pwd.encode())
        pwd = m.hexdigest()
        post_data = {
            'username': self._username,
            'password': pwd,
            'token': self._password,
            'randnumber': code,
            'isPasswordPolicy': '1',
        }

        try:
            r = self._s.post(BNUjwc._login_old_url, data=post_data)
        except ConnectionError as e:
            raise LoginError('连接失败：' + e.strerror)
        if r.status_code != 200:
            raise LoginError('登录提交失败！状态码：' + str(r.status_code))
        return json.loads(r.text)

    @staticmethod
    def _default_code_callback(code_img):
        code_img.show()
        return input()

    def get_cookies(self):
        return self._s.cookies

    def set_cookies(self, cookies):
        self._s.cookies = cookies

    def login(self, code_callback = None):
        """
        login
        :return: None
        """
        self._get_login_params()

        post_data = {
            'username': self._username,
            'password': self._password,
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
        if r.text.find('北京师范大学教务网络管理系统') != -1:
            code_img = jwc._get_validate_code()
            code = ''
            if code_callback:
                code = code_callback(code_img)
            else:
                code = BNUjwc._default_code_callback(code_img)
            self._login_old(code)

    def ready_for_threading(self):
        self._get_student_info()

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
        params = "xktype=3&xn=%s&xq=%s&xh=%s&nj=%s&zydm=%s&kcdm=%s&kclb1=%s&kclb2=%s&kclb3=" \
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
        params = "xktype=3&initQry=0&xh=%s&xn=%s&xq=%s&nj=%s&zydm=%s&" \
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

    def get_selection_result(self):
        """
        get selection result
        :return: {
            'semester': ['学年学期：2015-2016', '春季学期', '时间区段：2015-12-24 20:00→2016-01-15 23:59'],
            'modules': [{
                '模块': '学校平台/思想政治理论模块',
                '限选学分': '',
                '已选学分': '',
                '可选学分': '',
                '指定学分': '', # none
                '限选门数': '',
                '已选门数': '',
                '可选门数': '',
                '指定门数': '', # none
            }, ...],
            'courses': [{
                '上课时间地点': '1-16\xa0周四[9-10]\xa0八111',
                '类别': '大学外语模块',
                '课程': '[0410036171]跨文化交际英语课程',
                '已选人数': '35', '限选人数': '35',
                '学分': '2.0',
                '上课班级名称': '02班',
                '序号': '1',
                '可选人数': '0',
                '任课教师': '高秀琴',
                '上课班号': '02',
                '课程代码': '0410036171-02',
                '选课方式': '学生网上选'
            }, ...]
        }
        """
        r = self._s.get(BNUjwc._selection_result_url + str(random.random()))
        self._result_parser.feed(r.text)
        tables = self._result_parser.tables

        semester = re.split('\xa0+', tables[0][0][0])
        modules_title = ['模块', '限选学分', '已选学分', '可选学分', '指定学分', '限选门数', '已选门数', '可选门数', '指定门数']
        courses_title = ['序号', '课程', '学分', '类别', '任课教师', '上课班号', '上课班级名称', '选课方式',
                        '已选人数', '限选人数', '可选人数', '上课时间地点', '课程代码']

        module = [dict(zip(modules_title, x)) for x in tables[1]]
        courses = [dict(zip(courses_title, x)) for x in tables[2]]
        return {
            'semester': semester,
            'modules': module,
            'courses': courses
        }

    def get_exam_rounds(self):
        """
        get exam rounds
        return: [{
            'code': '2015,0,1', # year, semester, rounds
            'name': 'xxx考试', # description
        }, ...]
        """
        return json.loads(jwc._get_droplist('Ms_KSSW_FBXNXQKSLC'))

    def get_exam_arragement(self, exam):
        """
        get specific exam arrangement
        param exam: one exam from get_exam_rounds
        return: [{
            'xf': '1.0', # score
            'ksdd': '本部 风雨操场 健美室2', # where
            'khfs': '考试', # exam type
            'kssj': '2015-12-30(17周 星期三)13:30-15:10', # when
            'zwh': '18', # seat number
            'kc': '[1210041491]男子健美', # course name
            'lb': '学校平台/体育与健康模块', # course classification
        }, ...]
        """
        exam = exam['code']
        exam_info = exam.split(',')
        post_data = {
            'xh': '',
            'xn': exam_info[0],
            'xq': exam_info[1],
            'kslc': exam_info[2],
            'xnxqkslc': exam,
            'menucode_current': '',
        }
        print(self._get_table_list(BNUjwc._exam_arragement_table_id, post_data))

    def get_exam_scores(self, year = None, semester = None):
        """
        get specific exam scores
        param year: exam year
        param semester: exam semester 
                        (0: Autumn Semester, 1: Spring Semester, 2: Summer Semester)
        return: [{
            '辅修标记': '主修',
            '综合成绩': '82.0',
            '课程/环节': '[0410006991]大学英语ⅠB（读译）',
            '备注': '',
            '学分': '2.0',
            '类别': '公共课/必修课',
            '平时成绩': '84.4',
            '期末成绩': '78.5',
            '学年学期': '2014-2015学年秋季学期',
            '修读性质': '初修'
        }, ...]

        """
        self._get_student_info()

        post_data = {
            'sjxz': 'sjxz3',
            'ysyx': 'yscj',
            'userCode': self._info['xh'],
            'zfx': '0',
            'ysyxS': 'on',
            'sjxzS': 'on',
            'zfxS': 'on',
            'menucode_current': '',
        }

        if year == None:
            post_data['sjxz'] = 'sjxz1'
        elif year and semester:
            post_data['xn'] = year
            post_data['xn1'] = int(year) + 1
            post_data['xq'] = semester


        r = self._s.post(BNUjwc._exam_score_url, post_data)
        self._result_parser.feed(r.text, True)
        tables = self._result_parser.tables
        title = ['学年学期', '课程/环节', '学分', '类别', '修读性质', '平时成绩', '期末成绩', '综合成绩', '辅修标记', '备注']
        semester_title = ''
        scores = []
        if len(tables) <= 0:
            return self.get_exam_scores()
        for x in tables[0]:
            if x[0].strip():
                semester_title = x[0]
            else:
                x[0] = semester_title
            scores.append(dict(zip(title, x)))
        return scores

    def get_evaluate_list(self):
        """
        get teachers evaluating list
        return: [{
            'qsrq': '2015-12-14', # start date
            'sfwjpj': '1',
            'sfzbpj': '1',
            'xn': '2015', # year
            'xq_m': '0', # semester
            'pjfsbz': '0',
            'lcjc': '本科课堂教学终结评价', # name
            'lcqc': '2015-2016学年秋季学期', # semester name
            'jsrq': '2016-01-03', # end date
            'sfkpsj': '0', # 0 - cannot 1 - can
            'lcdm': '2015002' # code
        }, ...]
        """
        post_data = {
            'pjzt_m': 20
        }
        r = self._s.post(BNUjwc._evaluate_list_url, post_data)
        m = re.findall(r'<option value=\'({.*?})\'>(.*?)</option>', r.text)
        return [json.loads(data) for data, name in m]

    def get_evaluate_course_list(self, evaluate):
        """
        get teachers evaluating course list
        return: [{
            'pjlb_m': '01',
            'gh': '93106',
            'kcmc': '数字逻辑',
            'xm': '张钟军',
            'kcdm': '1610062781',
            'skbjdm': '1610062781-01',
            'pjlbmc': '理论课',
            'ypflag': '0',
            'yhdm': '1610062781',
            'xf': '3',
            'sfzjjs': '1',
            'jsid': '006346',
            'pjzt_m': '20'
        }, ...]
        """
        post_data = {
            'xn': evaluate['xn'],
            'xq': evaluate['xq_m'],
            'pjlc': evaluate['lcdm'],
            'sfzbpj': evaluate['sfzbpj'],
            'sfwjpj': evaluate['sfwjpj'],
            'pjzt_m': 20,
            'pjfsbz': evaluate['pjfsbz'],
            'menucode_current': '',
        }

        r = self._s.post(BNUjwc._table_url + BNUjwc._evaluate_course_list_table_id, data=post_data)
        m = re.findall(r'parent.jxpj\("(.*?)","', r.text)
        m = ','.join(m).replace('\\\"', '\"')
        m = '[' + m + ']'
        return json.loads(m)

    def evaluate_course(self, evaluate, course, score=5):
        """
        evaluate specific course
        param evaluate: evaluate round from get_evaluate_list
        param course: evaluate course from get_evaluate_course_list
        return: {'status': '200', 'result': None, 'message': '操作成功!'}
        """

        self._get_student_info()

        get_data = {
            'jsid': course['jsid'],
            'sfzjjs': course['sfzjjs'],
            'jsgh': course['gh'],
            'jsxm': course['xm'],
            'pjlb_m': course['pjlb_m'],
            'pjlbmc': course['pjlbmc'],
            'xn': evaluate['xn'],
            'xq': evaluate['xq_m'],
            'pjlc': evaluate['lcdm'],
            'kcdm': course['kcdm'],
            'kcmc': course['kcmc'],
            'xf': course['xf'],
            'userCode': self._info['xh'],
            'sfzbpj': evaluate['sfzbpj'],
            'sfwjpj': evaluate['sfwjpj'],
            'pjzt_m': course['pjzt_m'],
            'pjfsbz': evaluate['pjfsbz'],
            'ypflag': course['ypflag'],
            'mode': '0',
            'skbjdm': course['skbjdm'],
        }

        r = self._s.get(BNUjwc._evaluate_form_url, params=get_data)
        self._evaluate_parser.feed(r.text)

        if score > 5:
            score = 5
        elif score < 1:
            score = 1

        commit = ';'.join([str(score) + '@' + x + '@0' + str(6 - score) for x in self._evaluate_parser.select])
        commit = urllib.parse.quote(urllib.parse.quote(commit))

        commitText = []
        for x in self._evaluate_parser.text:
            if score < 2:
                commitText.append(x + '@#@优点很少，收获不多，建议老师充分调动课堂，创新教学方式，继续努力')
            else:
                commitText.append(x + '@#@优点很多，收获很多，没有建议，继续努力')

        commitText = ';'.join(commitText)
        commitText = urllib.parse.quote(urllib.parse.quote(commitText))
        
        post_data = {
            'wspjZbpjWjdcForm.pjlb_m': course['pjlb_m'],
            'wspjZbpjWjdcForm.sfzjjs': course['sfzjjs'],
            'wspjZbpjWjdcForm.xn': evaluate['xn'],
            'wspjZbpjWjdcForm.xq': evaluate['xq_m'],
            'wspjZbpjWjdcForm.pjlc': evaluate['lcdm'],
            'wspjZbpjWjdcForm.pjzt_m': course['pjzt_m'],
            'wspjZbpjWjdcForm.userCode': self._info['xh'],
            'wspjZbpjWjdcForm.kcdm': course['kcdm'],
            'wspjZbpjWjdcForm.skbjdm': course['skbjdm'],
            'wspjZbpjWjdcForm.pjfsbz': evaluate['pjfsbz'],
            'wspjZbpjWjdcForm.jsid': course['jsid'],
            'wspjZbpjWjdcForm.zbmb_m': '005',
            'wspjZbpjWjdcForm.wjmb_m': '002',
            'wspjZbpjWjdcForm.commitZB': commit,
            'wspjZbpjWjdcForm.commitWJText': commitText,
            'wspjZbpjWjdcForm.commitWJSelect': '',
            'pycc': 1,
            'menucode_current': '',
        }

        r = self._s.post(BNUjwc._evaluate_save_url, data=post_data)
        return json.loads(r.text)


if __name__ == '__main__':

    print("******************************")
    print("* 北京师范大学 教务助手 v0.2 *")
    print("* BNU Education Assistance   *")
    print("*                            *")
    print("* 作者:   许宏旭             *")
    print("* author: Hongxu Xu          *")
    print("*                  2016-3-6  *")
    print("******************************")

    print("登录中…")
    username = ''
    pwd = ''
    with open('user.txt', 'r') as f:
        username = f.readline().strip()
        pwd = f.readline().strip()
        jwc = BNUjwc(username, pwd)

    jwc.login()

    print('登录成功!')

    def select_by_plan():
        courses = jwc.get_plan_courses()
        for i, course in enumerate(courses):
            print(i, course)
        print('输入 -1 则退出')
        print('请输入课程序号以查看详情')
        i = int(input())
        if i == -1:
            return
        child_courses = jwc.view_plan_course(courses[i])
        for j, child_course in enumerate(child_courses):
            print(j, child_course)
        print('输入 -1 则退出')
        print('请输入课程序号以确认选课')
        j = int(input())
        if j == -1:
            return
        print(jwc.select_plan_course(courses[i], child_courses[j]))

    def select_elective_course():
        courses = jwc.get_elective_courses()
        for i, course in enumerate(courses):
            print(i, course)
        print('输入 -1 则退出')
        print('请输入课程序号以确认选课')
        i = int(input())
        if i == -1:
            return
        print(jwc.select_elective_course(courses[i]))

    def cancel_course():
        courses = jwc.get_cancel_courses()
        for i, course in enumerate(courses):
            print(i, course)
        print('输入 -1 则退出')
        print('请输入课程序号以确认退课')
        i = int(input())
        if i == -1:
            return
        print(jwc.cancel_course(courses[i]))

    def query_selection_result():
        result =  jwc.get_selection_result()
        print(json.dumps(result, ensure_ascii=False))

    def query_exam_arrangement():
        rounds = jwc.get_exam_rounds()
        for i, x in enumerate(rounds):
            print(i, x)
        print('输入 -1 则退出')
        print('请输入考试轮次序号以确认查询')
        i = int(input())
        if i == -1:
            return
        jwc.get_exam_arragement(rounds[i])

    def query_exam_scores():
        print("请输入学年(留空或查询不到则默认返回大学全部成绩):")
        year = input()
        semester = ''
        if year:
            print("请输入学期(0: 秋季学期, 1: 春季学期, 2: 夏季学期):")
            semester = input()
        print(jwc.get_exam_scores(year, semester))

    def evaluate_teachers():
        evaluate = jwc.get_evaluate_list()
        for i, x in enumerate(evaluate):
            print(i, x)
        print('输入 -1 则退出')
        print('请输入评教轮次序号以选择评教轮次')
        i = int(input())
        if i == -1:
            return
        course = jwc.get_evaluate_course_list(evaluate[i])
        for j, x in enumerate(course):
            print(j, x)
        print('输入 -1 则退出')
        print('输入 -2 则全部 5分 好评')
        print('请输入课程序号以选择评教课程老师')
        j = int(input())
        if j == -1:
            return
        elif j == -2:
             for j, x in enumerate(course):
                print(jwc.evaluate_course(evaluate[i], x))
             return
        print("请输入分值(1 ~ 5):")
        score = int(input())
        print(jwc.evaluate_course(evaluate[i], course[j], score))

    def view_wishlist():
        print('*** 愿望单 ***')
        print(" - 计划课程 - ")
        for x in wishlist['plan']:
            print(x)
        print(" - 公选课程 - ")
        for x in wishlist['elective']:
            print(x)

    def add_by_plan():
        courses = jwc.get_plan_courses()
        for i, course in enumerate(courses):
            print(i, course)
        print('输入 -1 则退出')
        print('请输入课程序号以查看详情')
        i = int(input())
        if i == -1:
            return
        child_courses = jwc.view_plan_course(courses[i])
        for j, child_course in enumerate(child_courses):
            print(j, child_course)
        print('输入 -1 则退出')
        print('请输入课程序号以确认添加')
        j = int(input())
        if j == -1:
            return
        wishlist['plan'].append((courses[i], child_courses[j]))
        print("已添加")

    def add_by_elective():
        courses = jwc.get_elective_courses()
        for i, course in enumerate(courses):
            print(i, course)
        print('输入 -1 则退出')
        print('请输入课程序号以确认添加')
        i = int(input())
        if i == -1:
            return
        wishlist['elective'].append(courses[i])
        print("已添加")

    def grab_courses():

        worklist = {
            'elective': wishlist['elective'][:],
            'plan': wishlist['plan'][:],
        }

        sleep_time = 1.2
        print('默认抢课间隔时间为', sleep_time, '秒')
        while len(worklist['elective']) + len(worklist['plan']):
            for course in worklist['elective'][:]:
                ret = jwc.select_elective_course(course)
                if ret['status'] == '300':
                    sleep_time += .2
                    print(course['kc'], '本次抢课失败, 重新加入抢课队列. 原因: 抢课过快, 延长间隔时间为', sleep_time, '秒')
                elif ret['message'].find('人数已满') != -1:
                    print(course['kc'], ret['message'], '重新加入抢课队列, 等待有人退课.')
                else:
                    worklist['elective'].remove(course)
                    print(course['kc'], ret['message'])
                if len(worklist['elective']) + len(worklist['plan']):
                    time.sleep(sleep_time)
            for course in worklist['plan'][:]:
                ret = jwc.select_plan_course(course[0], course[1])
                if ret['status'] == '300':
                    sleep_time += .2
                    print('抢课过快,延长间隔时间为', sleep_time, '秒')
                elif ret['message'].find('人数已满') != -1:
                    print(course['kc'], ret['message'], '重新加入抢课队列, 等待有人退课.')
                else:
                    worklist['plan'].remove(course)
                    print(course[0]['kc'], ret['message'])
                if len(worklist['elective']) + len(worklist['plan']):
                    time.sleep(sleep_time)

        print("完成")

    def bye():
        with open("wishlist.txt", "w+") as f:
            f.write(json.dumps(wishlist,ensure_ascii=False))
        print("已保存愿望单")
        print("再见")
        exit()

    first = True
    wishlist = {}

    try:
        with open("wishlist.txt", "r+") as f:
            wishlist = json.loads(f.read())
    except:
        with open("wishlist.txt", "w+") as f:
            f.write("")

    if not 'plan' in wishlist:
        wishlist = {
            'plan': [],
            'elective': [],
        }

    while True:

        if first:
            first = False
        else:
            print("******************************")
            print("* 北京师范大学 教务助手 v0.2 *")
            print("* BNU Schoolwork Assist      *")
            print("*                            *")
            print("* 作者:   许宏旭             *")
            print("* author: Hongxu Xu          *")
            print("*                  2016-3-6  *")
            print("******************************")

        print("\n请输入操作代号:")
        print("\n# 选课 #")
        print("0: 按开课计划选课")
        print("1: 选公共选修课")
        print("2: 退课")
        print("3: 查询选课结果")
        print("\n# 考试 #")
        print("4: 获取考试安排")
        print("5: 获取考试成绩")
        print("\n# 评教 #")
        print("6: 评教")
        print("\n*** 抢课 ***")
        print("- 添加愿望课程")
        print("\ta: 自开课计划")
        print("\tb: 自公选课")
        print("\tc: 查看愿望单")
        print("- 抢课")
        print("\tQ: 开始抢课")
        print("\n7: 退出\n")

        cmd = input()

        options = {
            "0": select_by_plan,
            "1": select_elective_course,
            "2": cancel_course,
            "3": query_selection_result,
            "4": query_exam_arrangement,
            "5": query_exam_scores,
            "6": evaluate_teachers,
            "a": add_by_plan,
            "b": add_by_elective,
            "c": view_wishlist,
            "Q": grab_courses,
            "7": bye,
        }

        options.get(cmd, lambda :print("无此命令!\n"))()

        print("\n\n请按下任意键继续……")
        input()

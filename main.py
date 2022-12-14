import datetime
from itertools import count
from socket import timeout
from PySide2.QtWidgets import QLabel, QWidget, QApplication
from PySide2.QtCore import QObject, QThread, Signal, Slot
import os
import shutil
import time
import sys
from math import isclose
import subprocess
from menu import Ui_Form
from ping3 import ping
import paramiko
from scp import SCPClient
from concurrent.futures import ThreadPoolExecutor
import json
import re
import datetime
import openpyxl

from PIL import Image

app_off = False


class Communicator(QObject):  # класс для передачи сигналов для прогресс бара(файлы)
    signal = Signal(int)


class Communicator2(QObject):  # класс для передачи сигналов для прогресс бара(IP)
    signal = Signal(int)


class SearchIp(QThread, QObject):
    def __init__(self, parent=None):
        QThread.__init__(self, parent)
        self.parent = parent
        self.comm2 = Communicator2()
        self.comm2.signal.connect(parent.progress_bar_foo2)
        self.ip_from_ip = Worker.ip_list(self)

    def getIp(self):
        self.parent.label.setText("")
        self.count = 0
        global app_off
        # self.touch_ip = {}
        self.done_ip_score = 0
        wb = openpyxl.load_workbook(
            filename=r"\\192.168.160.100\Winelab\Розница Винлаб\21. IT\03- Реестры\\Реестр магазинов SAP.xlsx"
        )
        sheet = wb["Реестр магазинов SAP"]
        count = 2
        none_count = 0
        self.ip_from_xls = []
        for row in sheet.values:
            if row[6] != None:
                for last_digit in range(10, 12):
                    unspace_ip = row[6].strip()
                    i = f"{unspace_ip[:-1]}{last_digit}"
                    self.ip_from_xls.append(i)
        del self.ip_from_xls[0:2]

        self.parent.setProgressMax(self.ip_from_xls)
        with ThreadPoolExecutor(max_workers=10) as e:
            jobs = [e.submit(self.touch_test, ii) for ii in self.ip_from_xls]
            e.shutdown()

        # json.dump(self.touch_ip, open("data" + os.sep + "touch_ip.json", "w"))
        # self.touch_ip = []
        if self.count == 0:
            self.parent.label.setText("Новых тачей нет")
        else:
            self.parent.label.setText("Новые IP внесены в ip.json")
        self.count = 0
        self.parent.ip_time_value.setText(
            MainWidget.ip_stat(self)
            + "  строк: "
            + MainWidget.rows_count(self, "ip.json")
        )

        self.parent.touch_count.setText(self.touch_count() + "шт.")
        json.dump(self.ip_from_ip, open("data" + os.sep + "ip.json", "w"))

    def touch_test(
        self, ip
    ):  # смотрим в каталог на кассе если есть папка web значит тач
        if app_off == True:
            return False
        self.done_ip_score += 1
        self.comm2.signal.emit(self.done_ip_score)
        if ip not in self.ip_from_ip:
            if Worker.online_test(self, ip):
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    client.connect(
                        hostname=ip,
                        username="tc",
                        password="324012",
                        port="22",
                        timeout=10,
                    )

                except:
                    return False
                stdin, stdout, stderr = client.exec_command(
                    "ls /mnt/sda1/tce/storage/crystal-cash"
                )

                data = str(stdout.read())
                client.close()

                if "WEB" in data or "web" in data:
                    self.ip_from_ip[ip] = "touch"
                    self.count += 1
                    self.parent.label.setText(f"Нашел новый ТАЧ по адресу : {ip}")
                    self.parent.touch_time_value.setText(f"{self.count}шт.")
                else:
                    self.ip_from_ip[ip] = "no_touch"
            else:
                self.ip_from_ip[ip] = "false"
        if ip in self.ip_from_ip:
            self.parent.label.setText(f"Такой ТАЧ уже в списке: {ip}")

    # def extend_ip(self):
    #     self.touch_ip = json.load(open("data" + os.sep + "touch_ip.json", "r"))

    #     self.ip_from_ip.update(self.touch_ip)
    #     print(len(self.ip_from_ip))
    #     json.dump(self.ip_from_ip, open("data" + os.sep + "ip.json", "w"))
    #     os.remove("data" + os.sep + "touch_ip.json")
    #     self.parent.ip_time_value.setText(
    #         MainWidget.ip_stat(self)
    #         + "  строк: "
    #         + MainWidget.rows_count(self, "ip.json")
    #     )

    #     self.parent.touch_count.setText(self.touch_count() + "шт.")
    #     self.touch_ip = []

    def touch_count(self):
        count = 0
        for i, y in self.ip_from_ip.items():
            if y == "touch":
                count += 1
        return str(count)

    def run(self):
        self.getIp()


class Worker(QThread, QLabel):
    def __init__(self, parent=None):
        QThread.__init__(self, parent)

        self.comm = Communicator()
        self.comm2 = Communicator2()
        self.comm.signal.connect(parent.progress_bar_foo)
        self.comm2.signal.connect(parent.progress_bar_foo2)
        self.slider_path = os.getcwd()
        self.data_path = os.path.join(self.slider_path, "data")
        self.slides_path = os.path.join(self.slider_path, "slides")
        self.score_file = 0
        self.score_ip = 0
        self.time_score = 0
        self.time_dur_sum = 0
        self.cashes = {}
        self.parent = parent
        self.err = False
        self.touch_ip = []
        self.touch_cashes = []

    def lineIpRead(self):  # считываем IP из поля ввода
        self.textRead = self.parent.ipValue.text()
        self.textRead = self.textRead.replace(" ", "")
        if self.textRead == "":  # если в поле пусто то берем IP из файла
            self.ip_list()  # то берем IP из файла
            self.thread_ip()

        elif re.findall(
            r"([0-9]{1,3}[\.]){3}[0-9]{1,3}", self.textRead
        ):  # если юзверь вписал IP
            self.cashes[self.textRead] = "touch"  # то в пусой список кладем введеный IP
            self.thread_ip()  # и копируем по IP
        else:
            self.parent.label.setText("Это не IP адрес !")
            time.sleep(2)
            self.parent.label.setText("")

    def write_log(self, access, ip):  # пишем лог
        time_string = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        with open(self.data_path + os.sep + "events.log", "a") as write_data:
            write_data.write(f"{time_string}  {ip} - {access} \n")

    def images_file_list(self):  # список имен файлов картинок
        self.file_list = os.listdir(self.slides_path)
        return self.file_list

    def rm_slides(self, ip):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=ip,
            username="tc",
            password="324012",
            port=22,
        )
        stdin, stdout, stderr = client.exec_command(
            "rm -rf /mnt/sda1/tce/storage/crystal-cash/web/assets/clients/Winelab/customerDisplay/slides"
        )

        stdin, stdout, stderr = client.exec_command(
            "mkdir -m 777 /mnt/sda1/tce/storage/crystal-cash/web/assets/clients/Winelab/customerDisplay/slides"
        )
        client.close()

    def ip_list(self):  # заполняем список IP из файла
        if os.path.exists("data" + os.sep + "ip.json"):
            self.cashes = json.load(open("data" + os.sep + "ip.json", "r"))
            return self.cashes
        else:
            return {}

    def online_test(self, ip):  # в сети касса или нет
        return ping(ip, timeout=1)

    def one_ip_duration(self, start, end):  # считаем время заливки картинок на один IP
        self.time_score += 1  # кол-во залитых IP
        self.dur_time = end - start
        self.time_dur_sum += float(
            str(self.dur_time).split(":")[2].strip("0")
        )  # суммируем время заливки на один IP в секундах
        self.middle_time_dur = (
            self.time_dur_sum / self.time_score
        )  # среднее время на один IP
        return self.middle_time_dur

    def touch_test(
        self, ip
    ):  # смотрим в каталог на кассе если есть папка web значит тач

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=ip,
                username="tc",
                password="324012",
                port="22",
                timeout=200,
                banner_timeout=200,
            )
        except:
            return False
        stdin, stdout, stderr = client.exec_command(
            "ls /mnt/sda1/tce/storage/crystal-cash"
        )
        data = str(stdout.read())
        client.close()
        if "WEB" in data or "web" in data:
            self.touch_ip.append(ip)
            return True
        else:
            return False

    def thread_ip(self):
        for k, v in self.cashes.items():
            if v == "touch":
                self.touch_cashes.append(k)
        self.parent.progressBar.setMaximum(len(self.images_file_list()))
        self.parent.progressBar2.setMaximum(len(self.touch_cashes))

        with ThreadPoolExecutor(max_workers=4) as s:
            jobs = [s.submit(self.copy_file, ip) for ip in self.touch_cashes]
            s.shutdown()
        if self.err:
            self.parent.label.setText("С ошибками ! См. лог")
        else:
            self.parent.label.setText("Готово !!!")

    def copy_file(self, ip):
        self.start_time = datetime.datetime.now()
        self.comm2.signal.emit(self.score_ip)
        self.score_file = 0
        self.score_ip += 1
        if self.online_test(ip):
            if self.touch_test(ip):
                self.rm_slides(ip)
                with ThreadPoolExecutor(max_workers=4) as e:
                    jobs = [
                        e.submit(self.threding_slides, ip, ii, self.slides_path)
                        for ii in self.images_file_list()
                    ]
                    e.shutdown()
                ssh = self.createSSHClient(ip, "22", "tc", "324012")
                scp = SCPClient(ssh.get_transport())
                scp.put(
                    r"%s" % self.slider_path + "/data/" + "slider.json",
                    r"/mnt/sda1/tce/storage/crystal-cash/web/config",
                )
                scp.put(
                    r"%s" % self.slider_path + "/data/" + "cfg.json",
                    r"/mnt/sda1/tce/storage/crystal-cash/web/config",
                )
                ssh.close()
                self.end_time = datetime.datetime.now()
                time_remaining = self.one_ip_duration(
                    self.start_time, self.end_time
                ) * (len(self.touch_cashes) - (list(self.touch_cashes).index(ip) + 1))
                time_remaining_m = int(float(time_remaining)) // 60
                time_remaining_s = int(float(time_remaining)) - time_remaining_m * 60
                self.parent.time_last.setText(
                    f"{str(time_remaining_m)}m {str(time_remaining_s)}s"
                )

        else:
            self.parent.label.setText("недоступна")
            self.err = True
            self.write_log(ip, "недоступен")

        self.comm2.signal.emit(self.score_ip)
        self.score_file = 0

    def json_func(self):
        cut_s, cut_l = set(), set()
        with open(
            self.data_path + os.sep + "slider.json", "r"
        ) as read_file:  # читаем шаблон json
            json_template = json.load(read_file)
            json_template = dict(json_template)

        for file in Worker.images_file_list(self):
            file = file.split("_")
            if file[1] == "S":
                cut_s.add(file[0] + "_" + file[1])
            if file[1] == "L":
                cut_l.add(file[0] + "_" + file[1])
        # вставляем новые значения
        json_template["open"]["images"]["slides"] = sorted(list(cut_l))
        json_template["closed"]["images"]["slides"] = sorted(list(cut_l))
        json_template["sale"]["images"]["slides"] = sorted(list(cut_s))
        with open(
            self.data_path + os.sep + "slider.json", "w"
        ) as write_file:  # записываем все назад в файло
            json.dump(json_template, write_file, indent=2)

    def createSSHClient(self, ip, port, user, password):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            ip,
            port,
            user,
            password,
            banner_timeout=60,
            timeout=60,
            auth_timeout=60,
        )
        return client

    def threding_slides(self, ip, ii, images_path):  # копируем картинку
        self.parent.label.setText(f"{ip}, {ii}")  # вывод IP и имени файла в Qt
        self.score_file += 1
        self.comm.signal.emit(
            self.score_file
        )  # значение в верхний progressBar(для каждого файла)
        ssh = self.createSSHClient(ip, "22", "tc", "324012")
        scp = SCPClient(ssh.get_transport())
        scp.put(
            r"%s" % images_path + "/" + ii,
            r"/mnt/sda1/tce/storage/crystal-cash/web/assets/clients/Winelab/customerDisplay/slides",
        )
        ssh.close()

    def run(self):
        self.json_func()
        self.lineIpRead()


class MainWidget(QWidget, Ui_Form):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.retranslateUi(self)
        self.slider_path = os.getcwd()
        self.data_path = os.path.join(self.slider_path, "data")
        self.slides_path = os.path.join(self.slider_path, "slides")
        self.worker = Worker(self)
        self.searchip = SearchIp(self)
        self.searchip.setTerminationEnabled(enabled=True)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(len(Worker.images_file_list(self)))
        self.progressBar.setValue(0)
        self.progressBar2.setMinimum(0)
        self.progressBar2.setMaximum(1)
        self.progressBar2.setValue(0)
        self.ip_time_value.setText(
            self.ip_stat() + "  строк: " + self.rows_count("ip.json")
        )

        self.touch_count.setText(self.searchip.touch_count() + "шт.")
        self.stop_prog = False

        self.label.setText("")
        self.delButton.clicked.connect(self.delPictures)
        self.clearButton.clicked.connect(self.clearIP)
        self.getIpButton.clicked.connect(self.searchip.start)
        # self.getSlides.clicked.connect(self.getSlides)
        self.downButton.clicked.connect(self.rename_slides)
        self.downButton.clicked.connect(self.worker.start)
        # self.ren_file_button.clicked.connect(self.searchip.extend_ip)

    # def rename_file(self):

    #     if os.path.exists(r"data\ip.txt") and os.path.exists(r"data\touch_ip.txt"):
    #         shutil.copyfile(r"data\ip.txt", r"data\old_ip.txt")
    #         os.remove(r"data\ip.txt")
    #         os.rename(r"data\touch_ip.txt", r"data\ip.txt")
    #         self.ip_time_value.setText(
    #             self.ip_stat() + "  строк: " + self.rows_count("ip.txt")
    #         )
    #         self.touch_time_value.setText(self.rows_count("touch_ip.txt" + "шт."))
    #         self.label.setText("Готово !")

    #     self.label.setText("Должно быть два файла ip и touch_ip !!!")

    def rows_count(self, file):
        c = 0
        if os.path.exists("data" + os.sep + file):
            rows = json.load(open("data" + os.sep + file, "r"))
            for i in rows:
                if rows[i] == "touch" or rows[i] == "no_touch":
                    c += 1
            return str(c)
        else:
            return "0"

    def ip_stat(self):
        if os.path.exists(r"data\ip.json"):
            ip_stat = os.stat("data\ip.json")
            return datetime.datetime.fromtimestamp(ip_stat.st_mtime).strftime(
                "%H:%M %d-%m-%Y"
            )
        else:
            return "файла ip.json нет"

    def touch_stat(self):
        if os.path.exists(r"data\touch_ip.json"):
            ip_stat = os.stat(r"data\touch_ip.json")
            return datetime.datetime.fromtimestamp(ip_stat.st_mtime).strftime(
                "%H:%M %d-%m-%Y"
            )
        else:
            return "файла touch_ip.json нет"

    def setProgressMax(self, i):
        self.progressBar2.setMaximum(len(i))

    def clearIP(self):  # чистит поле ввода IP
        self.ipValue.clear()

    def delPictures(self):  # вызывает win проводник
        subprocess.call(f"explorer {self.slides_path}")

    @Slot(int)
    def progress_bar_foo2(self, score_ip):
        self.progressBar2.setValue(score_ip)

    @Slot(int)
    def progress_bar_foo(self, score):
        self.progressBar.setValue(score)

    def rename_slides(
        self,
    ):  # ф-я переименовывает картинки под шаблон кассы  , по 4 штуки каждой с разными разрешениями
        list_dir = os.listdir(self.slides_path)
        if len(list_dir) % 4 != 0:
            self.label.setText("Кол-во картинок не кратно 4 !")
            pass

        try:
            os.mkdir(self.slides_path + os.sep + "tmp")
        except FileExistsError:
            pass
        list_of_resolution = {1366, 1280, 770, 856}  # разрешения для картинок
        file_number = 1
        # list_dir = os.listdir(slides_path)
        # перебираем картинки находим по одной каждого разрешения даем имена под одной цифрой по 4 файла и копируем в tmp
        # до тех пор пока файлы не закончатся, потом возвращаем переименованные файлы назад
        while len(list_dir) - 1 > 0:
            for res in list_of_resolution:
                list_dir = os.listdir(self.slides_path)
                for file in list_dir:
                    if os.path.isfile(os.path.join(self.slides_path, file)):
                        im = Image.open(
                            self.slides_path + os.sep + file
                        )  # читаем разрешение картинки
                        im.close()
                        if isclose(
                            res, im.size[0], abs_tol=10
                        ):  # разрешения картинок бывают с небольшим разбросом(+-10 пикселей)
                            if (
                                res == 1280
                            ):  # сравниваем разреш. картинок с нашим списком
                                file_name = (
                                    str(file_number) + "_" + "L" + "_" + "1280_800.jpg"
                                )
                            elif res == 1366:
                                file_name = (
                                    str(file_number) + "_" + "L" + "_" + "1366_768.jpg"
                                )
                            elif res == 770:
                                file_name = (
                                    str(file_number) + "_" + "S" + "_" + "1280_800.jpg"
                                )
                            elif res == 856:
                                file_name = (
                                    str(file_number) + "_" + "S" + "_" + "1366_768.jpg"
                                )

                            shutil.move(
                                self.slides_path + os.sep + file,
                                self.slides_path + os.sep + "tmp" + os.sep + file_name,
                            )
                            file_number += 1
                file_number = 1
        list_dir = os.listdir(self.slides_path + os.sep + "tmp")

        for file_name in list_dir:
            shutil.move(
                self.slides_path + os.sep + "tmp" + os.sep + file_name,
                self.slides_path + os.sep + file_name,
            )
        os.rmdir(self.slides_path + os.sep + "tmp")

    def closeEvent(self, event):
        global app_off
        app_off = True
        # self.searchip.quit()
        self.searchip.terminate()
        # self.searchip.requestInterruption()
        sys.exit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWidget()
    window.show()
    app.exec_()

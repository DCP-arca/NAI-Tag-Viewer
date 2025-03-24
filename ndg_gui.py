import json
import sys
import time

from io import BytesIO
from PIL import Image
from urllib import request

from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, QFileDialog, QLabel, QWidget, QTextEdit
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QProgressBar, QMessageBox, QDialog
from PyQt5.QtWidgets import QScrollArea  # 추가됨
from PyQt5.QtGui import QIcon, QPixmap, QImage
from PyQt5.QtCore import QSettings, QPoint, QSize, QCoreApplication

import NaiDictGetter
from prompt_converter import calculate_w_values

TITLE_NAME = "NAI Image Tag Viewer(with webui)"
TOP_NAME = "dcp_arca"
APP_NAME = "ndg_gui"

LABEL_TEXT_LIST = ["프롬프트(Prompt)",
                   "네거티브 프롬프트(Undesired Content)",
                   "변환된 프롬프트(Converted Prompt)",
                   "변환된 네거티브 프롬프트(Converted Undesired Content)",
                   "생성 옵션(AI Settings)",
                   "기타 정보"]

TEXTEDIT_HINT = "버튼 클릭 또는 아무 곳에 드래그 드랍하여 불러오기"


def prettify_dict(d):
    return json.dumps(d, sort_keys=True, indent=4)


def pil2pixmap(im):
    if im.mode == "RGB":
        r, g, b = im.split()
        im = Image.merge("RGB", (b, g, r))
    elif im.mode == "RGBA":
        r, g, b, a = im.split()
        im = Image.merge("RGBA", (b, g, r, a))
    elif im.mode == "L":
        im = im.convert("RGBA")
    # Bild in RGBA konvertieren, falls nicht bereits passiert
    im2 = im.convert("RGBA")
    data = im2.tobytes("raw", "RGBA")
    qim = QImage(
        data, im.size[0], im.size[1], QImage.Format_ARGB32)
    pixmap = QPixmap.fromImage(qim)
    return pixmap


class MyWidget(QMainWindow):

    def __init__(self, app):
        super().__init__()
        self.app = app

        self.init_window()
        self.init_content()
        self.show()

    def init_window(self):
        self.setWindowTitle(TITLE_NAME)
        self.settings = QSettings(TOP_NAME, APP_NAME)
        self.move(self.settings.value("pos", QPoint(300, 300)))
        self.resize(self.settings.value("size", QSize(512, 768)))
        self.setAcceptDrops(True)

    def init_content(self):
        # 메인 스크롤 영역 생성
        scroll_area = QScrollArea()
        self.setCentralWidget(scroll_area)
        
        # 스크롤 영역에 들어갈 컨테이너 위젯 생성
        container = QWidget()
        scroll_area.setWidget(container)
        scroll_area.setWidgetResizable(True)  # 위젯 크기 조절 가능하게 설정

        def add_titletext_and_textedit(vbox, titletext_content, stretch):
            label = QLabel(titletext_content, self)
            textedit = QTextEdit()
            textedit.setPlaceholderText(TEXTEDIT_HINT)
            textedit.setAcceptRichText(True)
            textedit.setAcceptDrops(False)
            vbox.addWidget(label)
            vbox.addWidget(textedit, stretch=stretch)
            return textedit

        vbox = QVBoxLayout(container)

        # Image section
        vbox_img = QVBoxLayout()
        vbox.addLayout(vbox_img)
        button_img = QPushButton(TEXTEDIT_HINT, self)
        button_img.setMinimumSize(QSize(500, 500))
        button_img.clicked.connect(self.show_select_dialog)
        button_img.setStyleSheet("""
QPushButton {
    padding: 5px;
    border-color: #FFFFFF;
    border-style: dotted;
    border-width: 5px;
    background-color: #FBEFEF;
}
            """)

        vbox_img.addWidget(button_img)
        self.button_img = button_img

        # Text edit boxes
        self.textedit_list = []
        
        # Original prompt
        self.textedit_list.append(
            add_titletext_and_textedit(vbox, LABEL_TEXT_LIST[0], 10))  # stretch 값 조정
        
        # Original negative prompt
        self.textedit_list.append(
            add_titletext_and_textedit(vbox, LABEL_TEXT_LIST[1], 10))  # stretch 값 조정
        
        # Add convert button section
        convert_hbox = QHBoxLayout()
        vbox.addLayout(convert_hbox)
        
        convert_button = QPushButton("변환하기 (Convert)", self)
        convert_button.clicked.connect(self.convert_prompts)
        convert_hbox.addWidget(convert_button)
        
        copy_prompt_button = QPushButton("변환된 프롬프트 복사", self)
        copy_prompt_button.clicked.connect(lambda: self.copy_to_clipboard(2))
        convert_hbox.addWidget(copy_prompt_button)
        
        copy_neg_button = QPushButton("변환된 네거티브 복사", self)
        copy_neg_button.clicked.connect(lambda: self.copy_to_clipboard(3))
        convert_hbox.addWidget(copy_neg_button)
        
        # Converted prompt
        self.textedit_list.append(
            add_titletext_and_textedit(vbox, LABEL_TEXT_LIST[2], 10))  # stretch 값 조정
        
        # Converted negative prompt
        self.textedit_list.append(
            add_titletext_and_textedit(vbox, LABEL_TEXT_LIST[3], 10))  # stretch 값 조정
        
        # Settings and other info
        self.textedit_list.append(
            add_titletext_and_textedit(vbox, LABEL_TEXT_LIST[4], 8))  # stretch 값 조정
        self.textedit_list.append(
            add_titletext_and_textedit(vbox, LABEL_TEXT_LIST[5], 5))

    def resizeEvent(self, event):
        # 윈도우 크기가 변경될 때 이미지 버튼 크기 조절
        window_width = self.width()
        if window_width < 500:
            self.button_img.setMinimumSize(QSize(window_width - 50, window_width - 50))
        else:
            self.button_img.setMinimumSize(QSize(500, 500))
        
        # 아이콘 크기 조절
        if hasattr(self, 'button_img') and self.button_img.icon():
            btn_size = self.button_img.size()
            self.button_img.setIconSize(
                QSize(int(btn_size.width() * 0.95), int(btn_size.height() * 0.95)))
                
        super().resizeEvent(event)

    def convert_prompts(self):
        # Get the current prompt and negative prompt
        prompt = self.textedit_list[0].toPlainText()
        neg_prompt = self.textedit_list[1].toPlainText()
        
        if not prompt and not neg_prompt:
            QMessageBox.information(self, '알림', "변환할 프롬프트가 없습니다.")
            return
        
        # Convert and set the results
        if prompt:
            converted_prompt = calculate_w_values(prompt)
            self.textedit_list[2].setText(converted_prompt)
        
        if neg_prompt:
            converted_neg_prompt = calculate_w_values(neg_prompt)
            self.textedit_list[3].setText(converted_neg_prompt)

    def copy_to_clipboard(self, index):
        clipboard = QApplication.clipboard()
        text = self.textedit_list[index].toPlainText()
        if text:
            clipboard.setText(text)
            QMessageBox.information(self, '알림', "클립보드에 복사되었습니다.")
        else:
            QMessageBox.information(self, '알림', "복사할 내용이 없습니다.")

    def execute_bystr(self, file_src):
        nai_dict, error_code = NaiDictGetter.get_naidict_from_file(file_src)
        print(nai_dict, error_code)

        self._execute_byinfo(nai_dict, error_code, file_src)

    def execute_byimg(self, img):
        nai_dict, error_code = NaiDictGetter.get_naidict_from_img(img)
        print(nai_dict, error_code)

        self._execute_byinfo(nai_dict, error_code, img)

    def _execute_byinfo(self, nai_dict, error_code, img_obj):
        if error_code == 0:
            QMessageBox.information(self, '경고', "EXIF가 존재하지 않는 파일입니다.")
        elif error_code == 1 or error_code == 2:
            QMessageBox.information(
                self, '경고', "EXIF는 존재하나 NAI/WebUI로부터 만들어진 것이 아닌 듯 합니다.")
            self.textedit_list[0].setText(str(nai_dict))
        elif error_code == 3:
            self.textedit_list[0].setText(nai_dict["prompt"])
            self.textedit_list[1].setText(nai_dict["negative_prompt"])
            
            # Clear converted prompts when loading new image
            self.textedit_list[2].clear()
            self.textedit_list[3].clear()
            
            self.textedit_list[4].setText(prettify_dict(nai_dict["option"]))
            self.textedit_list[5].setText(prettify_dict(nai_dict["etc"]))

            self.button_img.setStyleSheet("""
                padding: 5px;
                border-color: #FFFFFF;
                border-style: dotted;
                border-width: 5px;
                background-color: #FBEFEF;
                background-position: center;
            """)
            if isinstance(img_obj, str):
                qicon = QIcon(img_obj)
            else:
                pixmap = pil2pixmap(img_obj)
                qicon = QIcon(pixmap)

            self.button_img.setIcon(qicon)
            btn_size = self.button_img.size()
            self.button_img.setIconSize(
                QSize(int(btn_size.width() * 0.95), int(btn_size.height() * 0.95)))
            self.button_img.setText("")

    def show_select_dialog(self):
        select_dialog = QFileDialog()
        select_dialog.setFileMode(QFileDialog.ExistingFile)
        fname = select_dialog.getOpenFileNames(
            self, 'Open image file to get nai exif data', '', 'Image File(*.png *.webp)')

        if fname[0]:
            self.execute_bystr(fname[0][0])

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u for u in event.mimeData().urls()]

        if len(files) != 1:
            QMessageBox.information(self, '경고', "파일을 하나만 옮겨주세요.")
            return

        furl = files[0]
        if furl.isLocalFile():
            fname = furl.toLocalFile()
            if not fname.endswith(".png") and not fname.endswith(".webp"):
                QMessageBox.information(self, '경고', "png, webp 파일만 가능합니다.")
                return
            self.execute_bystr(fname)
        else:
            url = furl.url()
            res = request.urlopen(url).read()
            img = Image.open(BytesIO(res))
            if not img:
                QMessageBox.information(self, '경고', "이미지 파일 다운로드에 실패했습니다.")
                return
            self.execute_byimg(img)

    def closeEvent(self, e):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("size", self.size())
        e.accept()

    def quit_app(self):
        time.sleep(0.1)
        self.close()
        self.app.closeAllWindows()
        QCoreApplication.exit(0)


if __name__ == '__main__':
    input_list = sys.argv
    app = QApplication(sys.argv)
    widget = MyWidget(app)

    time.sleep(0.1)

    sys.exit(app.exec_())
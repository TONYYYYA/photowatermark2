import sys
import os
import json
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
                             QFileDialog, QComboBox, QSlider, QColorDialog, QInputDialog,
                             QMessageBox, QSpinBox, QCheckBox, QTabWidget, QGridLayout,
                             QGroupBox, QRadioButton, QDoubleSpinBox, QScrollArea)
from PyQt5.QtGui import QPixmap, QImage, QFontDatabase, QColor, QIcon, QPainter, QFont
from PyQt5.QtCore import Qt, QPoint, QSize

from PIL import Image, ImageDraw, ImageFont, ImageQt, ImageEnhance, ImageOps


class ImageWatermarkTool(QMainWindow):
    def __init__(self):
        super().__init__()
        # 窗口基础设置
        self.setWindowTitle("图片水印工具")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1200, 800)

        # 数据存储
        self.imported_images = []  # 存储导入的图片路径
        self.current_image_index = -1  # 当前选中图片索引
        self.current_image = None  # 当前处理的PIL图片对象
        self.is_dragging = False  # 是否正在拖拽水印
        self.templates_dir = Path.home() / ".watermark_templates"

        # 默认水印配置
        self.default_config = {
            # 水印类型配置
            "watermark_type": "text",  # "text" 或 "image"

            # 文本水印配置
            "text_content": "水印",
            "font_family": "Microsoft YaHei",
            "font_size": 48,
            "font_bold": False,
            "font_italic": False,
            "font_color": "#333333",
            "text_transparency": 60,
            "shadow": True,
            "shadow_color": "#FFFFFF",
            "shadow_offset": (2, 2),
            "stroke": False,
            "stroke_color": "#FFFFFF",
            "stroke_width": 1,

            # 图片水印配置
            "watermark_image_path": "",
            "image_scale": 30,  # 百分比
            "image_transparency": 60,

            # 布局配置
            "position": "bottom_right",  # 九宫格位置
            "custom_position": (90, 90),  # 自定义位置百分比
            "rotation": 0,  # 旋转角度

            # 导出配置
            "output_dir": "",
            "output_format": "png",
            "jpeg_quality": 90,
            "resize_mode": "none",  # none, width, height, percentage
            "resize_value": 100,
            "naming_mode": "original",  # original, prefix, suffix
            "prefix": "wm_",
            "suffix": "_watermarked"
        }

        # 加载保存的配置
        self.watermark_config = self.default_config.copy()
        self.load_saved_config()

        # 初始化界面
        self.init_ui()

        # 启用拖放
        self.setAcceptDrops(True)

    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)

        # 左侧：图片列表区域
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        left_panel.setMinimumWidth(220)

        # 标题
        left_title = QLabel("<h3>已导入图片</h3>")
        left_layout.addWidget(left_title)

        # 图片列表
        self.image_list = QListWidget()
        self.image_list.setViewMode(QListWidget.IconMode)
        self.image_list.setIconSize(QSize(120, 100))
        self.image_list.setResizeMode(QListWidget.Adjust)
        self.image_list.setSpacing(10)
        self.image_list.itemClicked.connect(self.on_image_selected)
        left_layout.addWidget(self.image_list)

        # 导入按钮
        import_buttons = QHBoxLayout()
        self.btn_import_single = QPushButton("导入单张")
        self.btn_import_batch = QPushButton("批量导入")
        self.btn_import_single.clicked.connect(lambda: self.import_images("single"))
        self.btn_import_batch.clicked.connect(lambda: self.import_images("batch"))
        import_buttons.addWidget(self.btn_import_single)
        import_buttons.addWidget(self.btn_import_batch)
        left_layout.addLayout(import_buttons)

        # 导出按钮
        self.btn_export = QPushButton("导出所有图片")
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setEnabled(False)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BBDEFB;
            }
        """)
        self.btn_export.clicked.connect(self.export_all_images)
        left_layout.addWidget(self.btn_export)

        main_layout.addWidget(left_panel)

        # 中间：预览区域
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setSpacing(15)

        # 预览标题
        preview_title = QLabel("<h3>预览窗口 (可拖拽水印调整位置)</h3>")
        center_layout.addWidget(preview_title)

        # 预览区域
        self.preview_container = QWidget()
        self.preview_container.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self.preview_layout = QVBoxLayout(self.preview_container)

        self.preview_label = QLabel("请导入图片")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(600, 500)
        self.preview_layout.addWidget(self.preview_label)

        # 添加滚动区域支持大图片
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.preview_container)
        scroll_area.setWidgetResizable(True)
        center_layout.addWidget(scroll_area, stretch=1)

        main_layout.addWidget(center_panel, stretch=3)

        # 右侧：设置面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMinimumWidth(350)

        # 设置标签页
        self.tabs = QTabWidget()

        # 1. 水印类型设置
        self.tab_watermark = QWidget()
        self.init_watermark_tab()
        self.tabs.addTab(self.tab_watermark, "水印类型")

        # 2. 布局设置
        self.tab_layout = QWidget()
        self.init_layout_tab()
        self.tabs.addTab(self.tab_layout, "水印布局")

        # 3. 导出设置
        self.tab_export = QWidget()
        self.init_export_tab()
        self.tabs.addTab(self.tab_export, "导出设置")

        # 4. 模板管理
        self.tab_templates = QWidget()
        self.init_templates_tab()
        self.tabs.addTab(self.tab_templates, "模板管理")

        right_layout.addWidget(self.tabs)
        main_layout.addWidget(right_panel, stretch=2)

    def init_watermark_tab(self):
        """初始化水印类型标签页"""
        layout = QVBoxLayout(self.tab_watermark)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # 水印类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("<b>水印类型：</b>"))
        self.radio_text = QRadioButton("文本水印")
        self.radio_image = QRadioButton("图片水印")

        if self.watermark_config["watermark_type"] == "text":
            self.radio_text.setChecked(True)
        else:
            self.radio_image.setChecked(True)

        self.radio_text.toggled.connect(self.on_watermark_type_changed)
        self.radio_image.toggled.connect(self.on_watermark_type_changed)

        type_layout.addWidget(self.radio_text)
        type_layout.addWidget(self.radio_image)
        layout.addLayout(type_layout)

        # 文本水印设置
        self.text_watermark_group = QGroupBox("文本水印设置")
        text_layout = QVBoxLayout(self.text_watermark_group)
        text_layout.setSpacing(12)

        # 文本内容
        text_content_layout = QHBoxLayout()
        text_content_layout.addWidget(QLabel("水印文本："))
        self.txt_watermark_text = QLineEdit()
        self.txt_watermark_text.setText(self.watermark_config["text_content"])
        self.txt_watermark_text.textChanged.connect(self.on_text_content_changed)
        text_content_layout.addWidget(self.txt_watermark_text)
        text_layout.addLayout(text_content_layout)

        # 字体选择
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("字体："))
        self.cmb_font = QComboBox()
        # 获取系统字体（修复字体获取方式）
        font_db = QFontDatabase()
        font_families = sorted(font_db.families())
        self.cmb_font.addItems(font_families)
        # 设置当前字体
        if self.watermark_config["font_family"] in font_families:
            self.cmb_font.setCurrentText(self.watermark_config["font_family"])
        self.cmb_font.currentTextChanged.connect(self.on_font_changed)
        font_layout.addWidget(self.cmb_font)
        text_layout.addLayout(font_layout)

        # 字号设置
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("字号："))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(8, 200)
        self.spin_font_size.setValue(self.watermark_config["font_size"])
        self.spin_font_size.valueChanged.connect(self.on_font_size_changed)
        font_size_layout.addWidget(self.spin_font_size)
        font_size_layout.addWidget(QLabel("px"))
        text_layout.addLayout(font_size_layout)

        # 字体样式
        font_style_layout = QHBoxLayout()
        self.chk_bold = QCheckBox("粗体")
        self.chk_italic = QCheckBox("斜体")
        self.chk_bold.setChecked(self.watermark_config["font_bold"])
        self.chk_italic.setChecked(self.watermark_config["font_italic"])
        self.chk_bold.stateChanged.connect(self.on_font_style_changed)
        self.chk_italic.stateChanged.connect(self.on_font_style_changed)
        font_style_layout.addWidget(self.chk_bold)
        font_style_layout.addWidget(self.chk_italic)
        text_layout.addLayout(font_style_layout)

        # 字体颜色
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("颜色："))
        self.btn_text_color = QPushButton()
        self.btn_text_color.setFixedSize(30, 30)
        self.btn_text_color.setStyleSheet(f"background-color: {self.watermark_config['font_color']}")
        self.btn_text_color.clicked.connect(self.choose_text_color)
        color_layout.addWidget(self.btn_text_color)
        text_layout.addLayout(color_layout)

        # 透明度
        alpha_layout = QHBoxLayout()
        alpha_layout.addWidget(QLabel("透明度："))
        self.slider_text_alpha = QSlider(Qt.Horizontal)
        self.slider_text_alpha.setRange(0, 100)
        self.slider_text_alpha.setValue(self.watermark_config["text_transparency"])
        self.lbl_text_alpha = QLabel(f"{100-self.watermark_config['text_transparency']}%")
        self.slider_text_alpha.valueChanged.connect(self.on_text_alpha_changed)
        alpha_layout.addWidget(self.slider_text_alpha)
        alpha_layout.addWidget(self.lbl_text_alpha)
        text_layout.addLayout(alpha_layout)

        # 文本效果
        effect_group = QGroupBox("文本效果")
        effect_layout = QVBoxLayout(effect_group)

        # 阴影
        shadow_layout = QHBoxLayout()
        self.chk_shadow = QCheckBox("添加阴影")
        self.chk_shadow.setChecked(self.watermark_config["shadow"])
        self.chk_shadow.stateChanged.connect(self.on_shadow_changed)
        shadow_layout.addWidget(self.chk_shadow)
        effect_layout.addLayout(shadow_layout)

        # 描边
        stroke_layout = QHBoxLayout()
        self.chk_stroke = QCheckBox("添加描边")
        self.chk_stroke.setChecked(self.watermark_config["stroke"])
        self.chk_stroke.stateChanged.connect(self.on_stroke_changed)
        stroke_layout.addWidget(self.chk_stroke)
        effect_layout.addLayout(stroke_layout)

        text_layout.addWidget(effect_group)
        layout.addWidget(self.text_watermark_group)

        # 图片水印设置
        self.image_watermark_group = QGroupBox("图片水印设置")
        image_layout = QVBoxLayout(self.image_watermark_group)
        image_layout.setSpacing(12)

        # 选择水印图片
        img_path_layout = QHBoxLayout()
        img_path_layout.addWidget(QLabel("水印图片："))
        self.txt_watermark_image = QLineEdit()
        self.txt_watermark_image.setText(self.watermark_config["watermark_image_path"])
        self.btn_select_watermark = QPushButton("浏览...")
        self.btn_select_watermark.clicked.connect(self.select_watermark_image)
        img_path_layout.addWidget(self.txt_watermark_image)
        img_path_layout.addWidget(self.btn_select_watermark)
        image_layout.addLayout(img_path_layout)

        # 缩放比例
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("缩放比例："))
        self.spin_image_scale = QSpinBox()
        self.spin_image_scale.setRange(5, 100)
        self.spin_image_scale.setValue(self.watermark_config["image_scale"])
        self.spin_image_scale.setSuffix("%")
        self.spin_image_scale.valueChanged.connect(self.on_image_scale_changed)
        scale_layout.addWidget(self.spin_image_scale)
        image_layout.addLayout(scale_layout)

        # 透明度
        img_alpha_layout = QHBoxLayout()
        img_alpha_layout.addWidget(QLabel("透明度："))
        self.slider_image_alpha = QSlider(Qt.Horizontal)
        self.slider_image_alpha.setRange(0, 100)
        self.slider_image_alpha.setValue(self.watermark_config["image_transparency"])
        self.lbl_image_alpha = QLabel(f"{self.watermark_config['image_transparency']}%")
        self.slider_image_alpha.valueChanged.connect(self.on_image_alpha_changed)
        img_alpha_layout.addWidget(self.slider_image_alpha)
        img_alpha_layout.addWidget(self.lbl_image_alpha)
        image_layout.addLayout(img_alpha_layout)

        layout.addWidget(self.image_watermark_group)

        # 根据当前水印类型显示对应设置
        self.update_watermark_type_visibility()

        # 添加拉伸项
        layout.addStretch(1)

    def init_layout_tab(self):
        """初始化水印布局标签页"""
        layout = QVBoxLayout(self.tab_layout)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # 位置设置
        position_group = QGroupBox("水印位置")
        position_layout = QVBoxLayout(position_group)

        # 九宫格位置选择
        grid_layout = QGridLayout()
        positions = [
            ("左上", "top_left"), ("中上", "top_center"), ("右上", "top_right"),
            ("左中", "middle_left"), ("居中", "center"), ("右中", "middle_right"),
            ("左下", "bottom_left"), ("中下", "bottom_center"), ("右下", "bottom_right")
        ]

        self.position_buttons = {}
        for i, (text, pos) in enumerate(positions):
            btn = QPushButton(text)
            btn.setMinimumHeight(30)
            btn.clicked.connect(lambda checked, p=pos: self.set_watermark_position(p))
            self.position_buttons[pos] = btn
            grid_layout.addWidget(btn, i // 3, i % 3)

        # 设置当前选中的位置按钮
        self.update_position_button_state()

        position_layout.addLayout(grid_layout)
        layout.addWidget(position_group)

        # 旋转设置
        rotation_layout = QHBoxLayout()
        rotation_layout.addWidget(QLabel("<b>旋转角度：</b>"))
        self.spin_rotation = QDoubleSpinBox()
        self.spin_rotation.setRange(-180, 180)
        self.spin_rotation.setDecimals(1)
        self.spin_rotation.setSingleStep(15)
        self.spin_rotation.setValue(self.watermark_config["rotation"])
        self.spin_rotation.valueChanged.connect(self.on_rotation_changed)
        rotation_layout.addWidget(self.spin_rotation)
        rotation_layout.addWidget(QLabel("°"))
        layout.addLayout(rotation_layout)

        # 添加拉伸项
        layout.addStretch(1)

    def init_export_tab(self):
        """初始化导出设置标签页"""
        layout = QVBoxLayout(self.tab_export)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # 输出文件夹
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(QLabel("<b>输出文件夹：</b>"))
        self.txt_output_dir = QLineEdit()
        self.txt_output_dir.setText(self.watermark_config["output_dir"])
        self.btn_select_output_dir = QPushButton("浏览...")
        self.btn_select_output_dir.clicked.connect(self.select_output_dir)
        output_dir_layout.addWidget(self.txt_output_dir)
        output_dir_layout.addWidget(self.btn_select_output_dir)
        layout.addLayout(output_dir_layout)

        # 输出格式
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("<b>输出格式：</b>"))
        self.cmb_output_format = QComboBox()
        self.cmb_output_format.addItems(["PNG", "JPEG"])
        self.cmb_output_format.setCurrentText(self.watermark_config["output_format"].upper())
        self.cmb_output_format.currentTextChanged.connect(self.on_output_format_changed)
        format_layout.addWidget(self.cmb_output_format)
        layout.addLayout(format_layout)

        # JPEG质量
        self.jpeg_quality_group = QWidget()
        jpeg_layout = QHBoxLayout(self.jpeg_quality_group)
        jpeg_layout.addWidget(QLabel("<b>JPEG质量：</b>"))
        self.slider_jpeg_quality = QSlider(Qt.Horizontal)
        self.slider_jpeg_quality.setRange(1, 100)
        self.slider_jpeg_quality.setValue(self.watermark_config["jpeg_quality"])
        self.lbl_jpeg_quality = QLabel(f"{self.watermark_config['jpeg_quality']}%")
        self.slider_jpeg_quality.valueChanged.connect(self.on_jpeg_quality_changed)
        jpeg_layout.addWidget(self.slider_jpeg_quality)
        jpeg_layout.addWidget(self.lbl_jpeg_quality)
        layout.addWidget(self.jpeg_quality_group)
        self.update_jpeg_quality_visibility()

        # 图片缩放
        resize_group = QGroupBox("图片缩放")
        resize_layout = QVBoxLayout(resize_group)

        resize_mode_layout = QHBoxLayout()
        resize_mode_layout.addWidget(QLabel("缩放模式："))
        self.cmb_resize_mode = QComboBox()
        self.cmb_resize_mode.addItems(["不缩放", "按宽度", "按高度", "按百分比"])
        mode_index = ["none", "width", "height", "percentage"].index(self.watermark_config["resize_mode"])
        self.cmb_resize_mode.setCurrentIndex(mode_index)
        self.cmb_resize_mode.currentIndexChanged.connect(self.on_resize_mode_changed)
        resize_mode_layout.addWidget(self.cmb_resize_mode)
        resize_layout.addLayout(resize_mode_layout)

        resize_value_layout = QHBoxLayout()
        resize_value_layout.addWidget(QLabel("缩放值："))
        self.spin_resize_value = QSpinBox()
        self.spin_resize_value.setRange(10, 500)
        self.spin_resize_value.setValue(self.watermark_config["resize_value"])
        self.spin_resize_value.valueChanged.connect(self.on_resize_value_changed)
        self.lbl_resize_unit = QLabel("像素" if self.watermark_config["resize_mode"] in ["width", "height"] else "%")
        resize_value_layout.addWidget(self.spin_resize_value)
        resize_value_layout.addWidget(self.lbl_resize_unit)
        resize_layout.addLayout(resize_value_layout)

        layout.addWidget(resize_group)

        # 文件名设置
        naming_group = QGroupBox("文件名设置")
        naming_layout = QVBoxLayout(naming_group)

        # 命名模式选择（单选）
        self.radio_original = QRadioButton("保留原文件名")
        self.radio_prefix = QRadioButton("添加自定义前缀")
        self.radio_suffix = QRadioButton("添加自定义后缀")

        if self.watermark_config["naming_mode"] == "original":
            self.radio_original.setChecked(True)
        elif self.watermark_config["naming_mode"] == "prefix":
            self.radio_prefix.setChecked(True)
        else:
            self.radio_suffix.setChecked(True)

        self.radio_original.toggled.connect(self.on_naming_mode_changed)
        self.radio_prefix.toggled.connect(self.on_naming_mode_changed)
        self.radio_suffix.toggled.connect(self.on_naming_mode_changed)

        naming_layout.addWidget(self.radio_original)
        naming_layout.addWidget(self.radio_prefix)
        naming_layout.addWidget(self.radio_suffix)

        # 前缀输入
        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("前缀："))
        self.txt_prefix = QLineEdit()
        self.txt_prefix.setText(self.watermark_config["prefix"])
        self.txt_prefix.textChanged.connect(self.on_prefix_changed)
        prefix_layout.addWidget(self.txt_prefix)
        naming_layout.addLayout(prefix_layout)

        # 后缀输入
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("后缀："))
        self.txt_suffix = QLineEdit()
        self.txt_suffix.setText(self.watermark_config["suffix"])
        self.txt_suffix.textChanged.connect(self.on_suffix_changed)
        suffix_layout.addWidget(self.txt_suffix)
        naming_layout.addLayout(suffix_layout)

        layout.addWidget(naming_group)

        # 更新输入框状态
        self.update_naming_input_state()

        # 添加拉伸项
        layout.addStretch(1)

    def init_templates_tab(self):
        """初始化模板管理标签页"""
        layout = QVBoxLayout(self.tab_templates)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # 模板列表
        self.template_list = QListWidget()
        layout.addWidget(QLabel("<b>已保存模板</b>"))
        layout.addWidget(self.template_list)

        # 加载现有模板
        self.load_templates()

        # 按钮布局
        btn_layout = QHBoxLayout()
        self.btn_save_template = QPushButton("保存当前设置")
        self.btn_load_template = QPushButton("加载选中模板")
        self.btn_delete_template = QPushButton("删除选中模板")

        self.btn_save_template.clicked.connect(self.save_current_as_template)
        self.btn_load_template.clicked.connect(self.load_selected_template)
        self.btn_delete_template.clicked.connect(self.delete_selected_template)

        btn_layout.addWidget(self.btn_save_template)
        btn_layout.addWidget(self.btn_load_template)
        btn_layout.addWidget(self.btn_delete_template)
        layout.addLayout(btn_layout)

        # 添加拉伸项
        layout.addStretch(1)

    def import_images(self, mode="single"):
        """导入图片"""
        file_paths = []

        if mode == "single":
            # 单张导入
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择图片", "",
                "图片文件 (*.jpg *.jpeg *.png *.bmp *.tiff *.tif);;所有文件 (*)"
            )
            if file_path:
                file_paths.append(file_path)
        else:
            # 批量导入 - 先尝试选择多个文件
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, "选择多张图片", "",
                "图片文件 (*.jpg *.jpeg *.png *.bmp *.tiff *.tif);;所有文件 (*)"
            )

            # 如果没有选择文件，尝试选择文件夹
            if not file_paths:
                dir_path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
                if dir_path:
                    for file in os.listdir(dir_path):
                        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')):
                            file_paths.append(os.path.join(dir_path, file))

        # 处理导入的图片
        if file_paths:
            new_count = 0
            for path in file_paths:
                if path not in self.imported_images:
                    self.imported_images.append(path)
                    new_count += 1

                    # 添加到列表显示
                    item = QListWidgetItem()
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        item.setIcon(QIcon(pixmap.scaled(120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                    item.setText(os.path.basename(path))
                    item.setData(Qt.UserRole, path)
                    self.image_list.addItem(item)

            # 如果是首次导入，自动选中第一张
            if self.current_image_index == -1 and self.imported_images:
                self.current_image_index = 0
                self.load_current_image()

            # 更新导出按钮状态
            self.btn_export.setEnabled(len(self.imported_images) > 0)

            if new_count > 0:
                QMessageBox.information(self, "导入成功", f"成功导入 {new_count} 张图片")

    def on_image_selected(self, item):
        """图片列表项被选中"""
        file_path = item.data(Qt.UserRole)
        if file_path in self.imported_images:
            self.current_image_index = self.imported_images.index(file_path)
            self.load_current_image()

    def load_current_image(self):
        """加载当前选中的图片"""
        if 0 <= self.current_image_index < len(self.imported_images):
            try:
                file_path = self.imported_images[self.current_image_index]
                self.current_image = Image.open(file_path).convert("RGBA")
                self.update_preview()
            except Exception as e:
                QMessageBox.warning(self, "加载失败", f"无法加载图片：{str(e)}")

    def update_preview(self):
        """更新预览窗口"""
        if not self.current_image:
            return

        # 创建带水印的预览图
        watermarked_image = self.apply_watermark(self.current_image.copy())

        # 转换为Qt可显示格式
        q_image = QImage(
            watermarked_image.tobytes(),
            watermarked_image.width, watermarked_image.height,
            QImage.Format_RGBA8888
        )
        pixmap = QPixmap.fromImage(q_image)

        # 调整大小以适应预览窗口，保持比例
        scaled_pixmap = pixmap.scaled(
            self.preview_label.width(), self.preview_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.preview_label.setPixmap(scaled_pixmap)

    def apply_watermark(self, image):
        """应用水印到图片"""
        # 创建水印图层
        watermark_layer = Image.new('RGBA', image.size, (255, 255, 255, 0))

        if self.watermark_config["watermark_type"] == "text":
            # 创建文本水印
            self.draw_text_watermark(watermark_layer)
        else:
            # 创建图片水印
            self.draw_image_watermark(watermark_layer)

        # 合并水印和原图
        return Image.alpha_composite(image, watermark_layer)

    def draw_text_watermark(self, layer):
        """绘制文本水印（修复了粗体和斜体问题）"""
        draw = ImageDraw.Draw(layer)
        text = self.watermark_config["text_content"]
        if not text:  # 防止空文本
            return

        # 加载基础字体
        try:
            font_path = self.get_font_path(self.watermark_config["font_family"])
            base_font = ImageFont.truetype(font_path, self.watermark_config["font_size"])
        except:
            #  fallback到默认字体
            base_font = ImageFont.load_default()

        # 创建临时图像来应用字体样式（粗体和斜体）
        temp_img = Image.new('RGBA', (layer.width, layer.height), (255, 255, 255, 0))
        temp_draw = ImageDraw.Draw(temp_img)

        # 绘制基础文本
        temp_draw.text((0, 0), text, font=base_font, fill=(0, 0, 0, 255))

        # 应用粗体效果
        if self.watermark_config["font_bold"]:
            # 通过偏移绘制多次实现粗体效果
            temp_draw.text((1, 0), text, font=base_font, fill=(0, 0, 0, 255))
            temp_draw.text((0, 1), text, font=base_font, fill=(0, 0, 0, 255))
            temp_draw.text((1, 1), text, font=base_font, fill=(0, 0, 0, 255))

        # 应用斜体效果
        if self.watermark_config["font_italic"]:
            # 通过旋转实现斜体效果
            temp_img = temp_img.rotate(-15, expand=True, resample=Image.BILINEAR)

        # 获取处理后的文本尺寸
        bbox = temp_img.getbbox()
        if not bbox:  # 文本为空或无法处理
            return

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 获取水印位置
        x, y = self.calculate_watermark_position(layer.size, (text_width, text_height))

        # 转换透明度（0-100到0-255）
        alpha = int(255 * (self.watermark_config["text_transparency"] / 100))

        # 解析颜色
        color = self.hex_to_rgba(self.watermark_config["font_color"], alpha)

        # 创建最终文本图层
        text_layer = Image.new('RGBA', layer.size, (255, 255, 255, 0))

        # 绘制阴影
        if self.watermark_config["shadow"]:
            shadow_color = self.hex_to_rgba(self.watermark_config["shadow_color"], alpha)
            offset_x, offset_y = self.watermark_config["shadow_offset"]

            # 创建阴影图层
            shadow_layer = Image.new('RGBA', temp_img.size, (255, 255, 255, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            shadow_draw.text((0, 0), text, font=base_font, fill=shadow_color)

            # 应用粗体到阴影
            if self.watermark_config["font_bold"]:
                shadow_draw.text((1, 0), text, font=base_font, fill=shadow_color)
                shadow_draw.text((0, 1), text, font=base_font, fill=shadow_color)
                shadow_draw.text((1, 1), text, font=base_font, fill=shadow_color)

            # 应用斜体到阴影
            if self.watermark_config["font_italic"]:
                shadow_layer = shadow_layer.rotate(-15, expand=True, resample=Image.BILINEAR)

            # 放置阴影
            text_layer.paste(shadow_layer, (x + offset_x - bbox[0], y + offset_y - bbox[1]), shadow_layer)

        # 绘制描边
        if self.watermark_config["stroke"]:
            stroke_color = self.hex_to_rgba(self.watermark_config["stroke_color"], alpha)
            stroke_width = self.watermark_config["stroke_width"]

            # 创建描边图层
            stroke_layer = Image.new('RGBA', temp_img.size, (255, 255, 255, 0))
            stroke_draw = ImageDraw.Draw(stroke_layer)

            # 绘制四周描边
            for dx in range(-stroke_width, stroke_width + 1):
                for dy in range(-stroke_width, stroke_width + 1):
                    if dx == 0 and dy == 0:
                        continue
                    stroke_draw.text((dx, dy), text, font=base_font, fill=stroke_color)

            # 应用斜体到描边
            if self.watermark_config["font_italic"]:
                stroke_layer = stroke_layer.rotate(-15, expand=True, resample=Image.BILINEAR)

            # 放置描边
            text_layer.paste(stroke_layer, (x - bbox[0], y - bbox[1]), stroke_layer)

        # 填充文本颜色
        colored_text = temp_img.copy()
        datas = colored_text.getdata()
        new_data = []
        for item in datas:
            if item[3] > 0:  # 如果像素不透明
                new_data.append(color)
            else:
                new_data.append((255, 255, 255, 0))
        colored_text.putdata(new_data)

        # 放置文本
        text_layer.paste(colored_text, (x - bbox[0], y - bbox[1]), colored_text)

        # 应用旋转
        if self.watermark_config["rotation"] != 0:
            rotated = text_layer.rotate(
                self.watermark_config["rotation"],
                expand=True,
                resample=Image.BILINEAR
            )
            # 创建新图层并粘贴旋转后的水印
            new_layer = Image.new('RGBA', layer.size, (255, 255, 255, 0))
            new_x = (layer.width - rotated.width) // 2
            new_y = (layer.height - rotated.height) // 2
            new_layer.paste(rotated, (new_x, new_y), rotated)
            layer.paste(new_layer)
        else:
            layer.paste(text_layer, (0, 0), text_layer)

    def draw_image_watermark(self, layer):
        """绘制图片水印"""
        image_path = self.watermark_config["watermark_image_path"]
        if not image_path or not os.path.exists(image_path):
            return

        try:
            # 加载水印图片并保持透明通道
            watermark = Image.open(image_path).convert("RGBA")

            # 计算缩放后的尺寸
            scale = self.watermark_config["image_scale"] / 100.0
            new_width = int(layer.width * scale)
            # 保持比例
            ratio = new_width / watermark.width
            new_height = int(watermark.height * ratio)

            # 缩放水印
            watermark = watermark.resize((new_width, new_height), Image.LANCZOS)

            # 调整透明度
            alpha = self.watermark_config["image_transparency"]
            r, g, b, a = watermark.split()
            a = a.point(lambda p: p * (alpha / 100.0))
            watermark.putalpha(a)

            # 应用旋转
            if self.watermark_config["rotation"] != 0:
                watermark = watermark.rotate(
                    self.watermark_config["rotation"],
                    expand=True,
                    resample=Image.BILINEAR
                )

            # 计算位置
            x, y = self.calculate_watermark_position(layer.size, watermark.size)

            # 绘制水印
            layer.paste(watermark, (x, y), watermark)

        except Exception as e:
            QMessageBox.warning(self, "水印错误", f"无法处理水印图片：{str(e)}")

    def calculate_watermark_position(self, image_size, watermark_size):
        """计算水印位置"""
        img_width, img_height = image_size
        wm_width, wm_height = watermark_size

        # 预设位置映射（百分比）
        position_map = {
            "top_left": (5, 5),
            "top_center": (50, 5),
            "top_right": (95, 5),
            "middle_left": (5, 50),
            "center": (50, 50),
            "middle_right": (95, 50),
            "bottom_left": (5, 95),
            "bottom_center": (50, 95),
            "bottom_right": (95, 95)
        }

        # 获取位置百分比
        if self.watermark_config["position"] in position_map:
            x_percent, y_percent = position_map[self.watermark_config["position"]]
        else:
            x_percent, y_percent = self.watermark_config["custom_position"]

        # 计算像素位置（居中对齐）
        x = int(img_width * x_percent / 100) - wm_width // 2
        y = int(img_height * y_percent / 100) - wm_height // 2

        # 确保水印在图片范围内
        x = max(0, min(x, img_width - wm_width))
        y = max(0, min(y, img_height - wm_height))

        return x, y

    def export_all_images(self):
        """导出所有图片"""
        output_dir = self.txt_output_dir.text().strip()

        # 检查输出目录
        if not output_dir:
            # 提示用户选择输出目录
            output_dir = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
            if not output_dir:
                return
            self.txt_output_dir.setText(output_dir)
            self.watermark_config["output_dir"] = output_dir

        # 检查是否为源文件夹
        if self.imported_images:
            source_dir = os.path.dirname(self.imported_images[0])
            if output_dir == source_dir:
                reply = QMessageBox.question(
                    self, "警告",
                    "不建议导出到源文件夹，可能会覆盖原图。是否继续？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

        # 导出进度
        success = 0
        failed = 0
        errors = []

        for img_path in self.imported_images:
            try:
                self.export_single_image(img_path, output_dir)
                success += 1
            except Exception as e:
                failed += 1
                errors.append(f"{os.path.basename(img_path)}: {str(e)}")

        # 显示结果
        msg = f"导出完成：成功 {success} 张，失败 {failed} 张"
        if failed > 0:
            msg += "\n错误详情：\n" + "\n".join(errors)
            QMessageBox.warning(self, "导出结果", msg)
        else:
            QMessageBox.information(self, "导出成功", msg)

    def export_single_image(self, img_path, output_dir):
        """导出单张图片"""
        # 打开原图
        try:
            image = Image.open(img_path).convert("RGBA")
        except Exception as e:
            raise Exception(f"无法打开图片: {str(e)}")

        # 应用水印
        watermarked = self.apply_watermark(image)

        # 调整大小
        resized = self.resize_image(watermarked)

        # 处理文件名
        filename = os.path.basename(img_path)
        name, ext = os.path.splitext(filename)

        # 根据命名模式处理（单选）
        if self.watermark_config["naming_mode"] == "prefix":
            new_name = f"{self.watermark_config['prefix']}{name}"
        elif self.watermark_config["naming_mode"] == "suffix":
            new_name = f"{name}{self.watermark_config['suffix']}"
        else:  # original
            new_name = name

        # 输出格式
        output_format = self.watermark_config["output_format"].lower()
        output_filename = f"{new_name}.{output_format}"
        output_path = os.path.join(output_dir, output_filename)

        # 处理文件重名
        counter = 1
        while os.path.exists(output_path):
            output_filename = f"{new_name}_{counter}.{output_format}"
            output_path = os.path.join(output_dir, output_filename)
            counter += 1

        # 保存图片
        try:
            if output_format == "jpeg":
                resized.convert("RGB").save(
                    output_path,
                    "JPEG",
                    quality=self.watermark_config["jpeg_quality"],
                    optimize=True
                )
            else:
                resized.save(output_path, "PNG")
        except Exception as e:
            raise Exception(f"保存失败: {str(e)}")

    def resize_image(self, image):
        """调整图片大小"""
        mode = self.watermark_config["resize_mode"]
        if mode == "none":
            return image

        width, height = image.size

        if mode == "percentage":
            # 按百分比缩放
            scale = self.watermark_config["resize_value"] / 100.0
            new_width = int(width * scale)
            new_height = int(height * scale)
        elif mode == "width":
            # 按宽度缩放
            new_width = self.watermark_config["resize_value"]
            ratio = new_width / width
            new_height = int(height * ratio)
        else:  # height
            # 按高度缩放
            new_height = self.watermark_config["resize_value"]
            ratio = new_height / height
            new_width = int(width * ratio)

        # 确保最小尺寸
        new_width = max(10, new_width)
        new_height = max(10, new_height)

        return image.resize((new_width, new_height), Image.LANCZOS)

    # 事件处理函数
    def on_watermark_type_changed(self):
        """水印类型变化"""
        if self.radio_text.isChecked():
            self.watermark_config["watermark_type"] = "text"
        else:
            self.watermark_config["watermark_type"] = "image"

        self.update_watermark_type_visibility()
        self.update_preview()

    def update_watermark_type_visibility(self):
        """更新水印类型可见性"""
        is_text = self.watermark_config["watermark_type"] == "text"
        self.text_watermark_group.setVisible(is_text)
        self.image_watermark_group.setVisible(not is_text)

    def on_text_content_changed(self, text):
        """文本内容变化"""
        self.watermark_config["text_content"] = text
        self.update_preview()

    def on_font_changed(self, font_name):
        """字体变化"""
        self.watermark_config["font_family"] = font_name
        self.update_preview()

    def on_font_size_changed(self, size):
        """字号变化"""
        self.watermark_config["font_size"] = size
        self.update_preview()

    def on_font_style_changed(self):
        """字体样式变化（粗体/斜体）"""
        self.watermark_config["font_bold"] = self.chk_bold.isChecked()
        self.watermark_config["font_italic"] = self.chk_italic.isChecked()
        self.update_preview()

    def choose_text_color(self):
        """选择文本颜色"""
        current_color = QColor(self.watermark_config["font_color"])
        color = QColorDialog.getColor(current_color, self, "选择文本颜色")

        if color.isValid():
            hex_color = color.name()
            self.watermark_config["font_color"] = hex_color
            self.btn_text_color.setStyleSheet(f"background-color: {hex_color}")
            self.update_preview()

    def on_text_alpha_changed(self, value):
        """文本透明度变化"""
        self.watermark_config["text_transparency"] = value
        self.lbl_text_alpha.setText(f"{value}%")
        self.update_preview()

    def on_shadow_changed(self, state):
        """阴影效果变化"""
        self.watermark_config["shadow"] = state == Qt.Checked
        self.update_preview()

    def on_stroke_changed(self, state):
        """描边效果变化"""
        self.watermark_config["stroke"] = state == Qt.Checked
        self.update_preview()

    def select_watermark_image(self):
        """选择水印图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择水印图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)"
        )
        if file_path:
            self.txt_watermark_image.setText(file_path)
            self.watermark_config["watermark_image_path"] = file_path
            self.update_preview()

    def on_image_scale_changed(self, value):
        """图片水印缩放变化"""
        self.watermark_config["image_scale"] = value
        self.update_preview()

    def on_image_alpha_changed(self, value):
        """图片水印透明度变化"""
        self.watermark_config["image_transparency"] = value
        self.lbl_image_alpha.setText(f"{value}%")
        self.update_preview()

    def set_watermark_position(self, position):
        """设置水印位置"""
        self.watermark_config["position"] = position
        self.update_position_button_state()
        self.update_preview()

    def update_position_button_state(self):
        """更新位置按钮状态"""
        current_pos = self.watermark_config["position"]
        for pos, btn in self.position_buttons.items():
            if pos == current_pos:
                btn.setStyleSheet("background-color: #cce5ff;")
            else:
                btn.setStyleSheet("")

    def on_rotation_changed(self, value):
        """旋转角度变化"""
        self.watermark_config["rotation"] = value
        self.update_preview()

    def select_output_dir(self):
        """选择输出文件夹"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if dir_path:
            self.txt_output_dir.setText(dir_path)
            self.watermark_config["output_dir"] = dir_path

    def on_output_format_changed(self, format_str):
        """输出格式变化"""
        self.watermark_config["output_format"] = format_str.lower()
        self.update_jpeg_quality_visibility()

    def update_jpeg_quality_visibility(self):
        """更新JPEG质量控件可见性"""
        is_jpeg = self.watermark_config["output_format"].lower() == "jpeg"
        self.jpeg_quality_group.setVisible(is_jpeg)

    def on_jpeg_quality_changed(self, value):
        """JPEG质量变化"""
        self.watermark_config["jpeg_quality"] = value
        self.lbl_jpeg_quality.setText(f"{value}%")

    def on_resize_mode_changed(self, index):
        """缩放模式变化"""
        modes = ["none", "width", "height", "percentage"]
        self.watermark_config["resize_mode"] = modes[index]

        # 更新单位标签
        if modes[index] in ["width", "height"]:
            self.lbl_resize_unit.setText("像素")
        else:
            self.lbl_resize_unit.setText("%")

        self.update_preview()

    def on_resize_value_changed(self, value):
        """缩放值变化"""
        self.watermark_config["resize_value"] = value
        self.update_preview()

    def on_naming_mode_changed(self):
        """命名模式变化（单选）"""
        if self.radio_original.isChecked():
            self.watermark_config["naming_mode"] = "original"
        elif self.radio_prefix.isChecked():
            self.watermark_config["naming_mode"] = "prefix"
        else:
            self.watermark_config["naming_mode"] = "suffix"

        self.update_naming_input_state()

    def update_naming_input_state(self):
        """更新命名输入框状态"""
        mode = self.watermark_config["naming_mode"]
        self.txt_prefix.setEnabled(mode == "prefix")
        self.txt_suffix.setEnabled(mode == "suffix")

    def on_prefix_changed(self, text):
        """前缀变化"""
        self.watermark_config["prefix"] = text

    def on_suffix_changed(self, text):
        """后缀变化"""
        self.watermark_config["suffix"] = text

    # 模板管理
    def load_templates(self):
        """加载所有模板"""
        self.template_list.clear()
        if not self.templates_dir.exists():
            return

        for file in self.templates_dir.glob("*.json"):
            if file.name != "last_config.json":
                item = QListWidgetItem(file.stem)
                self.template_list.addItem(item)

    def save_current_as_template(self):
        """保存当前设置为模板"""
        template_name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称：")
        if ok and template_name:
            # 确保模板目录存在
            if not self.templates_dir.exists():
                self.templates_dir.mkdir(parents=True, exist_ok=True)

            template_path = self.templates_dir / f"{template_name}.json"

            # 检查是否已存在
            if template_path.exists():
                reply = QMessageBox.question(
                    self, "确认覆盖",
                    f"模板 '{template_name}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            try:
                with open(template_path, "w", encoding="utf-8") as f:
                    json.dump(self.watermark_config, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "保存成功", f"模板 '{template_name}' 已保存")
                self.load_templates()
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"无法保存模板：{str(e)}")

    def load_selected_template(self):
        """加载选中的模板"""
        selected = self.template_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "未选择", "请先选择一个模板")
            return

        template_name = selected.text()
        template_path = self.templates_dir / f"{template_name}.json"

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 更新配置
            self.watermark_config = config

            # 更新界面
            self.update_ui_from_config()

            # 刷新预览
            self.update_preview()

            QMessageBox.information(self, "加载成功", f"已加载模板 '{template_name}'")
        except Exception as e:
            QMessageBox.warning(self, "加载失败", f"无法加载模板：{str(e)}")

    def delete_selected_template(self):
        """删除选中的模板"""
        selected = self.template_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "未选择", "请先选择一个模板")
            return

        template_name = selected.text()
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除模板 '{template_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        template_path = self.templates_dir / f"{template_name}.json"
        try:
            if template_path.exists():
                template_path.unlink()
            QMessageBox.information(self, "删除成功", f"模板 '{template_name}' 已删除")
            self.load_templates()
        except Exception as e:
            QMessageBox.warning(self, "删除失败", f"无法删除模板：{str(e)}")

    def update_ui_from_config(self):
        """从配置更新界面"""
        # 水印类型
        if self.watermark_config["watermark_type"] == "text":
            self.radio_text.setChecked(True)
        else:
            self.radio_image.setChecked(True)
        self.update_watermark_type_visibility()

        # 文本水印设置
        self.txt_watermark_text.setText(self.watermark_config["text_content"])
        self.cmb_font.setCurrentText(self.watermark_config["font_family"])
        self.spin_font_size.setValue(self.watermark_config["font_size"])
        self.chk_bold.setChecked(self.watermark_config["font_bold"])
        self.chk_italic.setChecked(self.watermark_config["font_italic"])
        self.btn_text_color.setStyleSheet(f"background-color: {self.watermark_config['font_color']}")
        self.slider_text_alpha.setValue(self.watermark_config["text_transparency"])
        self.lbl_text_alpha.setText(f"{self.watermark_config['text_transparency']}%")
        self.chk_shadow.setChecked(self.watermark_config["shadow"])
        self.chk_stroke.setChecked(self.watermark_config["stroke"])

        # 图片水印设置
        self.txt_watermark_image.setText(self.watermark_config["watermark_image_path"])
        self.spin_image_scale.setValue(self.watermark_config["image_scale"])
        self.slider_image_alpha.setValue(self.watermark_config["image_transparency"])
        self.lbl_image_alpha.setText(f"{self.watermark_config['image_transparency']}%")

        # 布局设置
        self.set_watermark_position(self.watermark_config["position"])
        self.spin_rotation.setValue(self.watermark_config["rotation"])

        # 导出设置
        self.txt_output_dir.setText(self.watermark_config["output_dir"])
        self.cmb_output_format.setCurrentText(self.watermark_config["output_format"].upper())
        self.update_jpeg_quality_visibility()
        self.slider_jpeg_quality.setValue(self.watermark_config["jpeg_quality"])
        self.lbl_jpeg_quality.setText(f"{self.watermark_config['jpeg_quality']}%")

        mode_index = ["none", "width", "height", "percentage"].index(self.watermark_config["resize_mode"])
        self.cmb_resize_mode.setCurrentIndex(mode_index)
        self.spin_resize_value.setValue(self.watermark_config["resize_value"])
        self.lbl_resize_unit.setText("像素" if self.watermark_config["resize_mode"] in ["width", "height"] else "%")

        if self.watermark_config["naming_mode"] == "original":
            self.radio_original.setChecked(True)
        elif self.watermark_config["naming_mode"] == "prefix":
            self.radio_prefix.setChecked(True)
        else:
            self.radio_suffix.setChecked(True)

        self.txt_prefix.setText(self.watermark_config["prefix"])
        self.txt_suffix.setText(self.watermark_config["suffix"])
        self.update_naming_input_state()

    # 拖放支持
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]

        # 处理文件夹
        all_files = []
        for path in file_paths:
            if os.path.isdir(path):
                for file in os.listdir(path):
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')):
                        all_files.append(os.path.join(path, file))
            else:
                if path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')):
                    all_files.append(path)

        if all_files:
            self.import_images_from_paths(all_files)

    def import_images_from_paths(self, file_paths):
        """从文件路径列表导入图片"""
        if not file_paths:
            return

        new_count = 0
        for path in file_paths:
            if path not in self.imported_images:
                self.imported_images.append(path)
                new_count += 1

                # 添加到列表显示
                item = QListWidgetItem()
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap.scaled(120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                item.setText(os.path.basename(path))
                item.setData(Qt.UserRole, path)
                self.image_list.addItem(item)

        # 如果是首次导入，自动选中第一张
        if self.current_image_index == -1 and self.imported_images:
            self.current_image_index = 0
            self.load_current_image()

        # 更新导出按钮状态
        self.btn_export.setEnabled(len(self.imported_images) > 0)

        if new_count > 0:
            QMessageBox.information(self, "导入成功", f"成功导入 {new_count} 张图片")

    # 鼠标事件 - 用于拖拽水印
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.preview_label.underMouse() and self.current_image:
            # 计算点击位置在原图中的百分比
            pos = self.preview_label.mapFromGlobal(event.globalPos())
            self.start_drag_position = pos
            self.is_dragging = True

    def mouseMoveEvent(self, event):
        if self.is_dragging and self.current_image:
            # 计算拖动位置在原图中的百分比
            pos = self.preview_label.mapFromGlobal(event.globalPos())
            pixmap = self.preview_label.pixmap()

            if pixmap and not pixmap.isNull():
                # 计算相对于预览图的比例
                scale_x = self.current_image.width / pixmap.width()
                scale_y = self.current_image.height / pixmap.height()

                # 计算在原图中的百分比位置
                x_percent = (pos.x() * scale_x / self.current_image.width) * 100
                y_percent = (pos.y() * scale_y / self.current_image.height) * 100

                # 限制在0-100范围内
                x_percent = max(0, min(100, x_percent))
                y_percent = max(0, min(100, y_percent))

                # 更新位置
                self.watermark_config["position"] = "custom"
                self.watermark_config["custom_position"] = (x_percent, y_percent)
                self.update_position_button_state()
                self.update_preview()

    def mouseReleaseEvent(self, event):
        self.is_dragging = False

    # 工具函数
    def hex_to_rgba(self, hex_str, alpha):
        """将十六进制颜色转换为RGBA元组"""
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c * 2 for c in hex_str])

        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        return (r, g, b, alpha)

    def get_font_path(self, font_name):
        """获取字体文件路径"""
        # 常见字体的默认路径
        font_paths = {
            "Microsoft YaHei": "C:/Windows/Fonts/msyh.ttc",
            "SimSun": "C:/Windows/Fonts/simsun.ttc",
            "SimHei": "C:/Windows/Fonts/simhei.ttf",
            "Arial": "C:/Windows/Fonts/arial.ttf",
            "Times New Roman": "C:/Windows/Fonts/times.ttf"
        }

        return font_paths.get(font_name, font_paths["SimSun"])

    # 配置保存与加载
    def load_saved_config(self):
        """加载保存的配置"""
        config_path = self.templates_dir / "last_config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    saved_config = json.load(f)
                    # 合并配置，确保所有键都存在
                    for key in self.default_config:
                        if key in saved_config:
                            self.watermark_config[key] = saved_config[key]
            except Exception as e:
                print(f"加载配置失败: {e}")
                # 继续使用默认配置

    def closeEvent(self, event):
        """窗口关闭时保存配置"""
        try:
            if not self.templates_dir.exists():
                self.templates_dir.mkdir(parents=True, exist_ok=True)

            config_path = self.templates_dir / "last_config.json"
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.watermark_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

        event.accept()


if __name__ == "__main__":
    # 确保中文显示正常
    import matplotlib

    matplotlib.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]

    app = QApplication(sys.argv)
    window = ImageWatermarkTool()
    window.show()
    sys.exit(app.exec_())

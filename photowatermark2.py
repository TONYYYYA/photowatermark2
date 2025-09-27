import sys
import os
import json
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
                             QFileDialog, QComboBox, QSlider, QColorDialog, QInputDialog,
                             QMessageBox, QSpinBox, QCheckBox, QTabWidget, QGridLayout)
from PyQt5.QtGui import QPixmap, QImage, QFont, QColor, QCursor, QIcon
from PyQt5.QtCore import Qt, QPoint, QSize, QMimeData
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops, ImageEnhance
import math

# 配置常量
DEFAULT_TEMPLATE = {
    "watermark_type": "text",  # "text" 或 "image"
    "text_content": "© 2025",
    "font_name": "Arial",
    "font_size": 36,
    "font_bold": False,
    "font_italic": False,
    "font_color": "#000000",
    "transparency": 50,
    "shadow": False,
    "shadow_color": "#FFFFFF",
    "shadow_blur": 2,
    "shadow_offset": (2, 2),
    "stroke": False,
    "stroke_color": "#FFFFFF",
    "stroke_width": 1,
    "image_path": "",
    "watermark_size": 50,  # 百分比
    "position": "bottom_right",
    "rotation": 0,
    "output_format": "same_as_input",
    "jpeg_quality": 80,
    "resize_mode": "none",
    "resize_value": 100,
    "custom_prefix": "wm_",
    "custom_suffix": "_watermarked"
}

POSITION_MAP = {
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

SUPPORTED_INPUT_FORMATS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif")


class WatermarkTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图片水印工具")
        self.setGeometry(100, 100, 1300, 800)
        self.setMinimumSize(1100, 700)

        # 初始化变量
        self.imported_images = []
        self.current_image_idx = -1
        self.current_image_pil = None
        self.current_watermark_pos = QPoint(0, 0)
        self.watermark_size = (0, 0)  # 水印尺寸
        self.is_dragging = False
        self.watermark_template = DEFAULT_TEMPLATE.copy()
        self.templates_dir = Path.home() / ".watermark_tool_templates"

        # 初始化模板目录和加载上次配置
        self.init_templates_dir()
        self.load_last_template()

        # 构建界面
        self.init_ui()

        # 确保关闭时保存配置
        self.destroyed.connect(self.save_last_template)

    def init_templates_dir(self):
        if not self.templates_dir.exists():
            try:
                self.templates_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "目录创建失败", f"无法创建模板目录：{str(e)}")

    def load_last_template(self):
        last_config_path = self.templates_dir / "last_config.json"
        if last_config_path.exists():
            try:
                with open(last_config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    # 合并配置，确保所有必要键存在
                    for key in DEFAULT_TEMPLATE:
                        if key not in loaded_config:
                            loaded_config[key] = DEFAULT_TEMPLATE[key]
                    self.watermark_template = loaded_config
            except Exception as e:
                QMessageBox.warning(self, "配置加载失败", f"无法加载上次配置：{str(e)}\n将使用默认配置")

    def save_last_template(self):
        last_config_path = self.templates_dir / "last_config.json"
        try:
            with open(last_config_path, "w", encoding="utf-8") as f:
                json.dump(self.watermark_template, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "配置保存失败", f"无法保存当前配置：{str(e)}")

    def init_ui(self):
        # 主容器
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # 左侧：图片列表区域
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)

        left_title = QLabel("<h3>已导入图片</h3>")
        left_layout.addWidget(left_title)

        self.image_list = QListWidget()
        self.image_list.setIconSize(QSize(100, 80))
        self.image_list.setResizeMode(QListWidget.Adjust)
        self.image_list.setViewMode(QListWidget.IconMode)
        self.image_list.itemClicked.connect(self.on_image_item_clicked)
        left_layout.addWidget(self.image_list, stretch=1)

        # 导入按钮
        import_btn_layout = QHBoxLayout()
        self.import_single_btn = QPushButton("导入单张图片")
        self.import_batch_btn = QPushButton("导入多张/文件夹")
        self.import_single_btn.clicked.connect(lambda: self.import_images(mode="single"))
        self.import_batch_btn.clicked.connect(lambda: self.import_images(mode="batch"))
        import_btn_layout.addWidget(self.import_single_btn)
        import_btn_layout.addWidget(self.import_batch_btn)
        left_layout.addLayout(import_btn_layout)

        # 导出按钮
        self.export_btn = QPushButton("导出所有图片")
        self.export_btn.clicked.connect(self.export_images)
        self.export_btn.setEnabled(False)
        left_layout.addWidget(self.export_btn)

        main_layout.addLayout(left_layout, stretch=1)

        # 中间：预览区域
        middle_layout = QVBoxLayout()
        middle_layout.setSpacing(10)

        middle_title = QLabel("<h3>图片预览（点击水印可拖拽）</h3>")
        middle_layout.addWidget(middle_title)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 2px solid #cccccc; background-color: #f8f8f8;")
        self.preview_label.setMinimumSize(600, 600)
        # 启用拖拽功能
        self.setAcceptDrops(True)
        middle_layout.addWidget(self.preview_label, stretch=1)

        main_layout.addLayout(middle_layout, stretch=3)

        # 右侧：设置标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setMinimumWidth(350)

        # 水印类型标签页
        self.watermark_type_tab = QWidget()
        self.init_watermark_type_tab()
        self.tab_widget.addTab(self.watermark_type_tab, "水印类型")

        # 水印布局标签页
        self.layout_tab = QWidget()
        self.init_layout_tab()
        self.tab_widget.addTab(self.layout_tab, "水印布局")

        # 导出设置标签页
        self.export_tab = QWidget()
        self.init_export_tab()
        self.tab_widget.addTab(self.export_tab, "导出设置")

        # 模板管理标签页
        self.template_tab = QWidget()
        self.init_template_tab()
        self.tab_widget.addTab(self.template_tab, "模板管理")

        main_layout.addWidget(self.tab_widget, stretch=2)

    def init_watermark_type_tab(self):
        layout = QVBoxLayout(self.watermark_type_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # 水印类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("<b>水印类型：</b>"))
        self.watermark_type_combo = QComboBox()
        self.watermark_type_combo.addItems(["文本水印", "图片水印"])
        if self.watermark_template["watermark_type"] == "image":
            self.watermark_type_combo.setCurrentText("图片水印")
        self.watermark_type_combo.currentTextChanged.connect(self.on_watermark_type_changed)
        type_layout.addWidget(self.watermark_type_combo)
        layout.addLayout(type_layout)

        # 文本水印设置组
        self.text_watermark_group = QWidget()
        text_layout = QVBoxLayout(self.text_watermark_group)
        text_layout.setSpacing(12)

        # 文本内容
        text_content_layout = QHBoxLayout()
        text_content_layout.addWidget(QLabel("<b>文本内容：</b>"))
        self.text_content_edit = QLineEdit()
        self.text_content_edit.setText(self.watermark_template["text_content"])
        self.text_content_edit.textChanged.connect(self.on_text_content_changed)
        text_content_layout.addWidget(self.text_content_edit)
        text_layout.addLayout(text_content_layout)

        # 字体设置
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("<b>字体：</b>"))
        self.font_combo = QComboBox()
        common_fonts = [
            "Arial", "Times New Roman", "Courier New",
            "Microsoft YaHei", "SimSun", "SimHei",
            "PingFang SC", "Songti SC", "Heiti SC"
        ]
        self.font_combo.addItems(common_fonts)
        self.font_combo.setCurrentText(self.watermark_template["font_name"])
        self.font_combo.currentTextChanged.connect(self.on_font_changed)
        font_layout.addWidget(self.font_combo)

        # 字号
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("<b>字号：</b>"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 200)
        self.font_size_spin.setValue(self.watermark_template["font_size"])
        self.font_size_spin.valueChanged.connect(self.on_font_size_changed)
        font_size_layout.addWidget(self.font_size_spin)
        font_layout.addLayout(font_size_layout)

        # 粗体/斜体
        font_style_layout = QHBoxLayout()
        self.bold_check = QCheckBox("粗体")
        self.bold_check.setChecked(self.watermark_template["font_bold"])
        self.bold_check.stateChanged.connect(self.on_font_style_changed)
        self.italic_check = QCheckBox("斜体")
        self.italic_check.setChecked(self.watermark_template["font_italic"])
        self.italic_check.stateChanged.connect(self.on_font_style_changed)
        font_style_layout.addWidget(self.bold_check)
        font_style_layout.addWidget(self.italic_check)
        font_layout.addLayout(font_style_layout)
        text_layout.addLayout(font_layout)

        # 字体颜色
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("<b>字体颜色：</b>"))
        self.color_btn = QPushButton()
        self.color_btn.setStyleSheet(f"background-color: {self.watermark_template['font_color']};")
        self.color_btn.setFixedSize(30, 30)
        self.color_btn.clicked.connect(self.choose_font_color)
        color_layout.addWidget(self.color_btn)
        text_layout.addLayout(color_layout)

        # 透明度
        alpha_layout = QHBoxLayout()
        alpha_layout.addWidget(QLabel("<b>透明度：</b>"))
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 100)
        self.alpha_slider.setValue(self.watermark_template["transparency"])
        self.alpha_slider.valueChanged.connect(self.on_transparency_changed)
        self.alpha_label = QLabel(f"{self.watermark_template['transparency']}%")
        alpha_layout.addWidget(self.alpha_slider)
        alpha_layout.addWidget(self.alpha_label)
        text_layout.addLayout(alpha_layout)

        # 增强样式
        style_group = QWidget()
        style_layout = QVBoxLayout(style_group)
        style_layout.addWidget(QLabel("<b>增强样式（可选）</b>"))

        # 阴影设置
        shadow_layout = QHBoxLayout()
        self.shadow_check = QCheckBox("添加阴影")
        self.shadow_check.setChecked(self.watermark_template["shadow"])
        self.shadow_check.stateChanged.connect(self.on_shadow_toggled)
        shadow_layout.addWidget(self.shadow_check)
        style_layout.addLayout(shadow_layout)

        # 描边设置
        stroke_layout = QHBoxLayout()
        self.stroke_check = QCheckBox("添加描边")
        self.stroke_check.setChecked(self.watermark_template["stroke"])
        self.stroke_check.stateChanged.connect(self.on_stroke_toggled)
        stroke_layout.addWidget(self.stroke_check)
        style_layout.addLayout(stroke_layout)

        text_layout.addWidget(style_group)
        layout.addWidget(self.text_watermark_group)

        # 图片水印设置组
        self.image_watermark_group = QWidget()
        self.image_watermark_group.setVisible(False)
        image_layout = QVBoxLayout(self.image_watermark_group)
        image_layout.setSpacing(12)

        # 选择图片水印
        image_path_layout = QHBoxLayout()
        image_path_layout.addWidget(QLabel("<b>水印图片：</b>"))
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setText(self.watermark_template["image_path"])
        self.image_path_btn = QPushButton("选择图片")
        self.image_path_btn.clicked.connect(self.choose_watermark_image)
        image_path_layout.addWidget(self.image_path_edit)
        image_path_layout.addWidget(self.image_path_btn)
        image_layout.addLayout(image_path_layout)

        # 图片水印大小
        image_size_layout = QHBoxLayout()
        image_size_layout.addWidget(QLabel("<b>水印大小：</b>"))
        self.image_size_slider = QSlider(Qt.Horizontal)
        self.image_size_slider.setRange(10, 200)
        self.image_size_slider.setValue(self.watermark_template["watermark_size"])
        self.image_size_slider.valueChanged.connect(self.on_image_size_changed)
        self.image_size_label = QLabel(f"{self.watermark_template['watermark_size']}%")
        image_size_layout.addWidget(self.image_size_slider)
        image_size_layout.addWidget(self.image_size_label)
        image_layout.addLayout(image_size_layout)

        # 图片水印透明度
        image_alpha_layout = QHBoxLayout()
        image_alpha_layout.addWidget(QLabel("<b>透明度：</b>"))
        image_alpha_layout.addWidget(self.alpha_slider)
        image_alpha_layout.addWidget(self.alpha_label)
        image_layout.addLayout(image_alpha_layout)

        layout.addWidget(self.image_watermark_group)

    def init_layout_tab(self):
        layout = QVBoxLayout(self.layout_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # 九宫格预设位置
        layout.addWidget(QLabel("<b>预设位置</b>"))
        position_grid = QWidget()
        position_layout = QGridLayout(position_grid)
        position_layout.setSpacing(8)

        positions = [
            ("左上", "top_left"), ("中上", "top_center"), ("右上", "top_right"),
            ("左中", "middle_left"), ("居中", "center"), ("右中", "middle_right"),
            ("左下", "bottom_left"), ("中下", "bottom_center"), ("右下", "bottom_right")
        ]
        for idx, (text, key) in enumerate(positions):
            row = idx // 3
            col = idx % 3
            btn = QPushButton(text)
            btn.setStyleSheet("padding: 8px 5px;")
            btn.clicked.connect(lambda _, k=key: self.set_watermark_position(k))
            position_layout.addWidget(btn, row, col)
        layout.addWidget(position_grid)

        # 旋转设置
        rotation_layout = QHBoxLayout()
        rotation_layout.addWidget(QLabel("<b>旋转角度：</b>"))
        self.rotation_spin = QSpinBox()
        self.rotation_spin.setRange(0, 360)
        self.rotation_spin.setValue(self.watermark_template["rotation"])
        self.rotation_spin.valueChanged.connect(self.on_rotation_changed)
        rotation_layout.addWidget(self.rotation_spin)
        rotation_layout.addWidget(QLabel("°"))
        layout.addLayout(rotation_layout)

    def init_export_tab(self):
        layout = QVBoxLayout(self.export_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # 输出文件夹
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(QLabel("<b>输出文件夹：</b>"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_btn = QPushButton("选择文件夹")
        self.output_dir_btn.clicked.connect(self.choose_output_dir)
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.output_dir_btn)
        layout.addLayout(output_dir_layout)

        # 输出格式
        output_format_layout = QHBoxLayout()
        output_format_layout.addWidget(QLabel("<b>输出格式：</b>"))
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["与原图一致", "JPEG", "PNG"])
        format_map = {"same_as_input": "与原图一致", "JPEG": "JPEG", "PNG": "PNG"}
        self.output_format_combo.setCurrentText(format_map[self.watermark_template["output_format"]])
        self.output_format_combo.currentTextChanged.connect(self.on_output_format_changed)
        output_format_layout.addWidget(self.output_format_combo)
        layout.addLayout(output_format_layout)

        # 命名规则
        layout.addWidget(QLabel("<b>文件命名规则</b>"))
        self.name_rule_combo = QComboBox()
        self.name_rule_combo.addItems(["保留原文件名", "添加自定义前缀", "添加自定义后缀"])
        self.name_rule_combo.currentIndexChanged.connect(self.on_name_rule_changed)
        layout.addWidget(self.name_rule_combo)

        # 前缀/后缀输入框
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText(f"输入前缀（默认：{self.watermark_template['custom_prefix']}）")
        self.prefix_edit.setText(self.watermark_template["custom_prefix"])
        self.prefix_edit.setVisible(False)
        self.prefix_edit.textChanged.connect(self.on_prefix_changed)
        layout.addWidget(self.prefix_edit)

        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText(f"输入后缀（默认：{self.watermark_template['custom_suffix']}）")
        self.suffix_edit.setText(self.watermark_template["custom_suffix"])
        self.suffix_edit.setVisible(False)
        self.suffix_edit.textChanged.connect(self.on_suffix_changed)
        layout.addWidget(self.suffix_edit)

        # JPEG质量
        self.jpeg_quality_group = QWidget()
        jpeg_quality_layout = QHBoxLayout(self.jpeg_quality_group)
        jpeg_quality_layout.addWidget(QLabel("<b>JPEG质量：</b>"))
        self.jpeg_quality_slider = QSlider(Qt.Horizontal)
        self.jpeg_quality_slider.setRange(0, 100)
        self.jpeg_quality_slider.setValue(self.watermark_template["jpeg_quality"])
        self.jpeg_quality_slider.valueChanged.connect(self.on_jpeg_quality_changed)
        self.jpeg_quality_label = QLabel(f"{self.watermark_template['jpeg_quality']}%")
        jpeg_quality_layout.addWidget(self.jpeg_quality_slider)
        jpeg_quality_layout.addWidget(self.jpeg_quality_label)
        self.update_jpeg_quality_visibility()
        layout.addWidget(self.jpeg_quality_group)

        # 图片缩放
        layout.addWidget(QLabel("<b>图片缩放（可选）</b>"))
        self.resize_mode_combo = QComboBox()
        self.resize_mode_combo.addItems(["不缩放", "按宽度缩放", "按高度缩放", "按百分比缩放"])
        mode_map = {"none": "不缩放", "width": "按宽度缩放", "height": "按高度缩放", "percent": "按百分比缩放"}
        self.resize_mode_combo.setCurrentText(mode_map[self.watermark_template["resize_mode"]])
        self.resize_mode_combo.currentTextChanged.connect(self.on_resize_mode_changed)
        layout.addWidget(self.resize_mode_combo)

        # 缩放值输入框
        self.resize_value_edit = QLineEdit()
        self.resize_value_edit.setPlaceholderText(self.get_resize_placeholder())
        self.resize_value_edit.setText(str(self.watermark_template["resize_value"]))
        self.resize_value_edit.textChanged.connect(self.on_resize_value_changed)
        layout.addWidget(self.resize_value_edit)

    def init_template_tab(self):
        layout = QVBoxLayout(self.template_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # 模板列表
        layout.addWidget(QLabel("<b>已保存模板</b>"))
        self.template_list = QListWidget()
        self.load_template_list()
        layout.addWidget(self.template_list, stretch=1)

        # 模板操作按钮
        btn_layout = QHBoxLayout()
        self.save_template_btn = QPushButton("保存当前配置为模板")
        self.save_template_btn.clicked.connect(self.save_template)
        self.load_template_btn = QPushButton("加载选中模板")
        self.load_template_btn.clicked.connect(self.load_template)
        self.delete_template_btn = QPushButton("删除选中模板")
        self.delete_template_btn.clicked.connect(self.delete_template)
        btn_layout.addWidget(self.save_template_btn)
        btn_layout.addWidget(self.load_template_btn)
        btn_layout.addWidget(self.delete_template_btn)
        layout.addLayout(btn_layout)

    # 事件处理函数
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path) and file_path.lower().endswith(SUPPORTED_INPUT_FORMATS):
                if file_path not in self.imported_images:
                    self.imported_images.append(file_path)
            elif os.path.isdir(file_path):
                for root, _, files in os.walk(file_path):
                    for file in files:
                        if file.lower().endswith(SUPPORTED_INPUT_FORMATS):
                            full_path = os.path.join(root, file)
                            if full_path not in self.imported_images:
                                self.imported_images.append(full_path)

        if self.imported_images:
            self.update_image_list()
            self.export_btn.setEnabled(True)
            if self.current_image_idx == -1:
                self.current_image_idx = 0
                self.load_current_image()

    def import_images(self, mode="single"):
        options = QFileDialog.Options()
        file_paths = []

        if mode == "single":
            path, _ = QFileDialog.getOpenFileName(
                self, "选择单张图片", "",
                "Image Files (*.jpg *.jpeg *.png *.bmp *.tiff *.tif)",
                options=options
            )
            if path:
                file_paths = [path]
        else:
            choice = QMessageBox.question(
                self, "选择导入方式", "请选择：\n【是】导入多张图片\n【否】导入整个文件夹",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if choice == QMessageBox.Yes:
                paths, _ = QFileDialog.getOpenFileNames(
                    self, "选择多张图片", "",
                    "Image Files (*.jpg *.jpeg *.png *.bmp *.tiff *.tif)",
                    options=options
                )
                file_paths = paths
            elif choice == QMessageBox.No:
                dir_path = QFileDialog.getExistingDirectory(self, "选择图片文件夹", options=options)
                if dir_path:
                    for root, _, files in os.walk(dir_path):
                        for file in files:
                            if file.lower().endswith(SUPPORTED_INPUT_FORMATS):
                                file_paths.append(os.path.join(root, file))

        new_images = [p for p in file_paths if p not in self.imported_images]
        if new_images:
            self.imported_images.extend(new_images)
            self.update_image_list()
            self.export_btn.setEnabled(True)
            if self.current_image_idx == -1:
                self.current_image_idx = 0
                self.load_current_image()

    def update_image_list(self):
        self.image_list.clear()
        for img_path in self.imported_images:
            item = QListWidgetItem()
            item.setText(os.path.basename(img_path))
            item.setSizeHint(QSize(120, 100))

            pixmap = QPixmap(img_path).scaled(
                100, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            item.setIcon(QIcon(pixmap))
            self.image_list.addItem(item)

    def on_image_item_clicked(self, item):
        index = self.image_list.row(item)
        if 0 <= index < len(self.imported_images):
            self.current_image_idx = index
            self.load_current_image()

    def load_current_image(self):
        if 0 <= self.current_image_idx < len(self.imported_images):
            img_path = self.imported_images[self.current_image_idx]
            try:
                self.current_image_pil = Image.open(img_path).convert("RGBA")
                self.update_preview()
            except Exception as e:
                QMessageBox.warning(self, "图片加载失败", f"无法打开图片 {os.path.basename(img_path)}：{str(e)}")
                self.imported_images.pop(self.current_image_idx)
                self.current_image_idx = max(0, self.current_image_idx - 1)
                self.update_image_list()
                if self.imported_images:
                    self.load_current_image()
                else:
                    self.export_btn.setEnabled(False)

    def create_watermark_layer(self, image_size):
        """创建水印图层"""
        # 创建透明图层
        watermark_layer = Image.new('RGBA', image_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark_layer)

        if self.watermark_template["watermark_type"] == "text":
            # 文本水印
            text = self.watermark_template["text_content"]
            if not text:
                return watermark_layer

            font_name = self.watermark_template["font_name"]
            font_size = self.watermark_template["font_size"]

            # 尝试加载字体
            try:
                font = ImageFont.truetype(font_name, font_size)
            except:
                # 如果指定字体无法加载，使用默认字体
                font = ImageFont.load_default()

            # 获取文本尺寸
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            self.watermark_size = (text_width, text_height)

            # 计算水印位置（基于原图尺寸）
            pos_x, pos_y = self.calculate_watermark_position(image_size)

            # 颜色处理
            color_hex = self.watermark_template["font_color"]
            r = int(color_hex[1:3], 16)
            g = int(color_hex[3:5], 16)
            b = int(color_hex[5:7], 16)
            alpha = int(255 * (self.watermark_template["transparency"] / 100))

            # 旋转处理
            if self.watermark_template["rotation"] != 0:
                # 创建临时图像用于旋转
                temp_img = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)

                # 绘制文本到临时图像
                if self.watermark_template["stroke"]:
                    stroke_color_hex = self.watermark_template["stroke_color"]
                    sr = int(stroke_color_hex[1:3], 16)
                    sg = int(stroke_color_hex[3:5], 16)
                    sb = int(stroke_color_hex[5:7], 16)
                    temp_draw.text((0, 0), text, font=font, fill=(r, g, b, alpha),
                                   stroke_width=self.watermark_template["stroke_width"],
                                   stroke_fill=(sr, sg, sb, alpha))
                else:
                    temp_draw.text((0, 0), text, font=font, fill=(r, g, b, alpha))

                # 旋转临时图像
                rotated = temp_img.rotate(self.watermark_template["rotation"], expand=True)

                # 计算旋转后的位置偏移
                rotated_width, rotated_height = rotated.size
                pos_x -= (rotated_width - text_width) // 2
                pos_y -= (rotated_height - text_height) // 2

                # 将旋转后的图像粘贴到水印图层
                watermark_layer.paste(rotated, (int(pos_x), int(pos_y)), rotated)
            else:
                # 不旋转，直接绘制
                if self.watermark_template["shadow"]:
                    shadow_color_hex = self.watermark_template["shadow_color"]
                    sr = int(shadow_color_hex[1:3], 16)
                    sg = int(shadow_color_hex[3:5], 16)
                    sb = int(shadow_color_hex[5:7], 16)
                    # 绘制阴影
                    shadow_x = pos_x + self.watermark_template["shadow_offset"][0]
                    shadow_y = pos_y + self.watermark_template["shadow_offset"][1]
                    draw.text((shadow_x, shadow_y), text, font=font, fill=(sr, sg, sb, alpha))

                if self.watermark_template["stroke"]:
                    stroke_color_hex = self.watermark_template["stroke_color"]
                    sr = int(stroke_color_hex[1:3], 16)
                    sg = int(stroke_color_hex[3:5], 16)
                    sb = int(stroke_color_hex[5:7], 16)
                    draw.text((pos_x, pos_y), text, font=font, fill=(r, g, b, alpha),
                              stroke_width=self.watermark_template["stroke_width"],
                              stroke_fill=(sr, sg, sb, alpha))
                else:
                    draw.text((pos_x, pos_y), text, font=font, fill=(r, g, b, alpha))

        else:
            # 图片水印
            image_path = self.watermark_template["image_path"]
            if not image_path or not os.path.exists(image_path):
                return watermark_layer

            try:
                # 打开水印图片
                watermark_img = Image.open(image_path).convert("RGBA")

                # 计算缩放后的尺寸
                scale = self.watermark_template["watermark_size"] / 100
                new_width = int(watermark_img.width * scale)
                new_height = int(watermark_img.height * scale)
                watermark_img = watermark_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.watermark_size = (new_width, new_height)

                # 调整透明度
                alpha = self.watermark_template["transparency"] / 100
                if alpha < 1.0:
                    r, g, b, a = watermark_img.split()
                    a = ImageEnhance.Brightness(a).enhance(alpha)
                    watermark_img = Image.merge('RGBA', (r, g, b, a))

                # 旋转处理
                if self.watermark_template["rotation"] != 0:
                    watermark_img = watermark_img.rotate(self.watermark_template["rotation"], expand=True)
                    self.watermark_size = (watermark_img.width, watermark_img.height)

                # 计算位置并粘贴水印
                pos_x, pos_y = self.calculate_watermark_position(image_size)
                watermark_layer.paste(watermark_img, (int(pos_x), int(pos_y)), watermark_img)

            except Exception as e:
                QMessageBox.warning(self, "水印图片错误", f"无法处理水印图片：{str(e)}")
                return watermark_layer

        return watermark_layer

    def calculate_watermark_position(self, image_size):
        """计算水印在原图上的位置"""
        if self.current_image_idx == -1 or not self.current_image_pil:
            return (0, 0)

        # 如果是通过拖拽设置的位置，直接使用
        if self.current_watermark_pos.x() != 0 or self.current_watermark_pos.y() != 0:
            # 计算预览窗口到原图的缩放比例
            preview_size = self.preview_label.size()
            img_width, img_height = self.current_image_pil.size
            scale_x = img_width / preview_size.width()
            scale_y = img_height / preview_size.height()

            return (self.current_watermark_pos.x() * scale_x, self.current_watermark_pos.y() * scale_y)

        # 否则使用预设位置
        pos_key = self.watermark_template["position"]
        if pos_key not in POSITION_MAP:
            pos_key = "bottom_right"

        x_percent, y_percent = POSITION_MAP[pos_key]
        img_width, img_height = image_size

        # 计算基于百分比的位置
        x = (img_width * x_percent / 100) - (self.watermark_size[0] / 2)
        y = (img_height * y_percent / 100) - (self.watermark_size[1] / 2)

        return (x, y)

    def update_preview(self):
        if self.current_image_pil is None:
            return

        preview_pil = self.current_image_pil.copy()
        watermark_layer = self.create_watermark_layer(preview_pil.size)
        if watermark_layer is None:
            return

        # 计算缩放比例
        preview_size = self.preview_label.size()
        img_size = preview_pil.size
        scale = min(preview_size.width() / img_size[0], preview_size.height() / img_size[1])
        scaled_img_size = (int(img_size[0] * scale), int(img_size[1] * scale))

        try:
            # 叠加水印
            watermarked_pil = Image.alpha_composite(preview_pil, watermark_layer)
            # 缩放到预览大小
            watermarked_pil_scaled = watermarked_pil.resize(scaled_img_size, Image.Resampling.LANCZOS)
            # 转换为QPixmap显示
            q_image = QImage(
                watermarked_pil_scaled.tobytes(),
                scaled_img_size[0], scaled_img_size[1],
                QImage.Format_RGBA8888
            )
            pixmap = QPixmap.fromImage(q_image)
            self.preview_label.setPixmap(pixmap)

            # 初始化水印位置
            self.init_watermark_position(preview_pil.size, scaled_img_size, scale)

        except Exception as e:
            QMessageBox.warning(self, "预览错误", f"无法生成预览：{str(e)}")

    def init_watermark_position(self, original_size, scaled_size, scale):
        """初始化水印在预览窗口中的位置"""
        pos_key = self.watermark_template["position"]
        if pos_key not in POSITION_MAP:
            pos_key = "bottom_right"

        x_percent, y_percent = POSITION_MAP[pos_key]

        # 计算预览窗口中的位置
        x = (scaled_size[0] * x_percent / 100) - (self.watermark_size[0] * scale / 2)
        y = (scaled_size[1] * y_percent / 100) - (self.watermark_size[1] * scale / 2)

        self.current_watermark_pos = QPoint(int(x), int(y))

    def on_preview_mouse_press(self, event):
        if event.button() == Qt.LeftButton and self.current_image_pil:
            # 检查点击是否在水印区域
            if self.is_point_on_watermark(event.pos()):
                self.is_dragging = True

    def on_preview_mouse_move(self, event):
        if self.is_dragging and self.current_image_pil:
            self.current_watermark_pos = event.pos()
            self.update_preview()

    def on_preview_mouse_release(self, event):
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            # 更新模板中的位置为"custom"表示用户自定义位置
            self.watermark_template["position"] = "custom"

    def is_point_on_watermark(self, point):
        """判断点击是否在水印区域"""
        if not self.current_image_pil or self.watermark_size[0] == 0 or self.watermark_size[1] == 0:
            return False

        # 计算水印区域
        half_width = int(self.watermark_size[0] * self.get_scale_factor() / 2)
        half_height = int(self.watermark_size[1] * self.get_scale_factor() / 2)

        # 考虑旋转
        rotation = self.watermark_template["rotation"]
        if rotation != 0:
            # 简化处理：使用旋转后的边界框
            rad = math.radians(rotation)
            cos_rad = abs(math.cos(rad))
            sin_rad = abs(math.sin(rad))

            rotated_width = int(self.watermark_size[0] * cos_rad + self.watermark_size[1] * sin_rad)
            rotated_height = int(self.watermark_size[0] * sin_rad + self.watermark_size[1] * cos_rad)

            half_width = rotated_width // 2
            half_height = rotated_height // 2

        # 判断点是否在水印区域内
        return (abs(point.x() - self.current_watermark_pos.x()) <= half_width and
                abs(point.y() - self.current_watermark_pos.y()) <= half_height)

    def get_scale_factor(self):
        """获取原图到预览窗口的缩放因子"""
        if not self.current_image_pil:
            return 1.0

        preview_size = self.preview_label.size()
        img_width, img_height = self.current_image_pil.size

        return min(preview_size.width() / img_width, preview_size.height() / img_height)

    def set_watermark_position(self, pos_key):
        self.watermark_template["position"] = pos_key
        self.current_watermark_pos = QPoint(0, 0)  # 重置拖拽位置
        self.update_preview()

    # 水印类型设置相关函数
    def on_watermark_type_changed(self, text):
        is_text = text == "文本水印"
        self.text_watermark_group.setVisible(is_text)
        self.image_watermark_group.setVisible(not is_text)
        self.watermark_template["watermark_type"] = "text" if is_text else "image"
        self.update_preview()

    def on_text_content_changed(self, text):
        self.watermark_template["text_content"] = text
        self.update_preview()

    def on_font_changed(self, font_name):
        self.watermark_template["font_name"] = font_name
        self.update_preview()

    def on_font_size_changed(self, size):
        self.watermark_template["font_size"] = size
        self.update_preview()

    def on_font_style_changed(self, state):
        self.watermark_template["font_bold"] = self.bold_check.isChecked()
        self.watermark_template["font_italic"] = self.italic_check.isChecked()
        self.update_preview()

    def choose_font_color(self):
        color = QColorDialog.getColor(QColor(self.watermark_template["font_color"]), self, "选择字体颜色")
        if color.isValid():
            color_hex = color.name()
            self.watermark_template["font_color"] = color_hex
            self.color_btn.setStyleSheet(f"background-color: {color_hex};")
            self.update_preview()

    def on_transparency_changed(self, value):
        self.watermark_template["transparency"] = value
        self.alpha_label.setText(f"{value}%")
        self.update_preview()

    def on_shadow_toggled(self, checked):
        self.watermark_template["shadow"] = checked
        self.update_preview()

    def on_stroke_toggled(self, checked):
        self.watermark_template["stroke"] = checked
        self.update_preview()

    def choose_watermark_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择水印图片", "",
            "Image Files (*.jpg *.jpeg *.png *.bmp *.tiff *.tif)",
            options=QFileDialog.Options()
        )
        if path:
            self.image_path_edit.setText(path)
            self.watermark_template["image_path"] = path
            self.update_preview()

    def on_image_size_changed(self, value):
        self.watermark_template["watermark_size"] = value
        self.image_size_label.setText(f"{value}%")
        self.update_preview()

    # 布局设置相关函数
    def on_rotation_changed(self, value):
        self.watermark_template["rotation"] = value
        self.update_preview()

    # 导出设置相关函数
    def choose_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出文件夹", options=QFileDialog.Options())
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def on_output_format_changed(self, text):
        format_map = {"与原图一致": "same_as_input", "JPEG": "JPEG", "PNG": "PNG"}
        self.watermark_template["output_format"] = format_map.get(text, "same_as_input")
        self.update_jpeg_quality_visibility()

    def update_jpeg_quality_visibility(self):
        visible = self.watermark_template["output_format"] == "JPEG"
        self.jpeg_quality_group.setVisible(visible)

    def on_name_rule_changed(self, index):
        self.prefix_edit.setVisible(index == 1)  # 索引1是"添加自定义前缀"
        self.suffix_edit.setVisible(index == 2)  # 索引2是"添加自定义后缀"

    def on_prefix_changed(self, text):
        self.watermark_template["custom_prefix"] = text

    def on_suffix_changed(self, text):
        self.watermark_template["custom_suffix"] = text

    def on_jpeg_quality_changed(self, value):
        self.watermark_template["jpeg_quality"] = value
        self.jpeg_quality_label.setText(f"{value}%")

    def on_resize_mode_changed(self, text):
        mode_map = {"不缩放": "none", "按宽度缩放": "width", "按高度缩放": "height", "按百分比缩放": "percent"}
        self.watermark_template["resize_mode"] = mode_map.get(text, "none")
        self.resize_value_edit.setPlaceholderText(self.get_resize_placeholder())

    def get_resize_placeholder(self):
        mode = self.watermark_template["resize_mode"]
        if mode == "width":
            return "输入宽度（像素）"
        elif mode == "height":
            return "输入高度（像素）"
        elif mode == "percent":
            return "输入百分比（1-200）"
        return ""

    def on_resize_value_changed(self, text):
        try:
            value = int(text)
            if (self.watermark_template["resize_mode"] == "percent" and 1 <= value <= 200) or \
                    (self.watermark_template["resize_mode"] in ["width", "height"] and value > 0):
                self.watermark_template["resize_value"] = value
        except ValueError:
            pass

    # 模板管理相关函数
    def load_template_list(self):
        self.template_list.clear()
        if not self.templates_dir.exists():
            return

        for file in self.templates_dir.glob("*.json"):
            if file.name != "last_config.json":
                self.template_list.addItem(file.stem)

    def save_template(self):
        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称：")
        if ok and name:
            template_path = self.templates_dir / f"{name}.json"
            if template_path.exists():
                reply = QMessageBox.question(
                    self, "覆盖模板", "同名模板已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            try:
                with open(template_path, "w", encoding="utf-8") as f:
                    json.dump(self.watermark_template, f, ensure_ascii=False, indent=2)
                self.load_template_list()
                QMessageBox.information(self, "保存成功", f"模板 '{name}' 已保存")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"无法保存模板：{str(e)}")

    def load_template(self):
        current_item = self.template_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "选择模板", "请先选择一个模板")
            return

        template_name = current_item.text()
        template_path = self.templates_dir / f"{template_name}.json"

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                self.watermark_template = json.load(f)

            # 更新UI以反映加载的模板
            self.update_ui_from_template()
            self.update_preview()
            QMessageBox.information(self, "加载成功", f"模板 '{template_name}' 已加载")
        except Exception as e:
            QMessageBox.warning(self, "加载失败", f"无法加载模板：{str(e)}")

    def update_ui_from_template(self):
        """从模板更新UI控件"""
        # 水印类型
        is_text = self.watermark_template["watermark_type"] == "text"
        self.watermark_type_combo.setCurrentText("文本水印" if is_text else "图片水印")
        self.text_watermark_group.setVisible(is_text)
        self.image_watermark_group.setVisible(not is_text)

        # 文本水印设置
        self.text_content_edit.setText(self.watermark_template["text_content"])
        self.font_combo.setCurrentText(self.watermark_template["font_name"])
        self.font_size_spin.setValue(self.watermark_template["font_size"])
        self.bold_check.setChecked(self.watermark_template["font_bold"])
        self.italic_check.setChecked(self.watermark_template["font_italic"])
        self.color_btn.setStyleSheet(f"background-color: {self.watermark_template['font_color']};")
        self.alpha_slider.setValue(self.watermark_template["transparency"])
        self.alpha_label.setText(f"{self.watermark_template['transparency']}%")
        self.shadow_check.setChecked(self.watermark_template["shadow"])
        self.stroke_check.setChecked(self.watermark_template["stroke"])

        # 图片水印设置
        self.image_path_edit.setText(self.watermark_template["image_path"])
        self.image_size_slider.setValue(self.watermark_template["watermark_size"])
        self.image_size_label.setText(f"{self.watermark_template['watermark_size']}%")

        # 布局设置
        self.rotation_spin.setValue(self.watermark_template["rotation"])

        # 导出设置
        format_map = {"same_as_input": "与原图一致", "JPEG": "JPEG", "PNG": "PNG"}
        self.output_format_combo.setCurrentText(format_map[self.watermark_template["output_format"]])
        self.update_jpeg_quality_visibility()
        self.jpeg_quality_slider.setValue(self.watermark_template["jpeg_quality"])
        self.jpeg_quality_label.setText(f"{self.watermark_template['jpeg_quality']}%")

        mode_map = {"none": "不缩放", "width": "按宽度缩放", "height": "按高度缩放", "percent": "按百分比缩放"}
        self.resize_mode_combo.setCurrentText(mode_map[self.watermark_template["resize_mode"]])
        self.resize_value_edit.setText(str(self.watermark_template["resize_value"]))
        self.resize_value_edit.setPlaceholderText(self.get_resize_placeholder())

        # 前缀/后缀
        self.prefix_edit.setText(self.watermark_template["custom_prefix"])
        self.suffix_edit.setText(self.watermark_template["custom_suffix"])

    def delete_template(self):
        current_item = self.template_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "选择模板", "请先选择一个模板")
            return

        template_name = current_item.text()
        reply = QMessageBox.question(
            self, "删除模板", f"确定要删除模板 '{template_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            template_path = self.templates_dir / f"{template_name}.json"
            if template_path.exists():
                try:
                    os.remove(template_path)
                    self.load_template_list()
                    QMessageBox.information(self, "删除成功", f"模板 '{template_name}' 已删除")
                except Exception as e:
                    QMessageBox.warning(self, "删除失败", f"无法删除模板：{str(e)}")

    # 导出图片函数
    def export_images(self):
        output_dir = self.output_dir_edit.text()
        if not output_dir:
            QMessageBox.warning(self, "选择输出文件夹", "请先选择输出文件夹")
            return

        if not os.path.exists(output_dir):
            QMessageBox.warning(self, "文件夹不存在", "所选输出文件夹不存在")
            return

        # 检查是否尝试导出到原文件夹
        for img_path in self.imported_images:
            img_dir = os.path.dirname(img_path)
            if os.path.abspath(output_dir) == os.path.abspath(img_dir):
                QMessageBox.warning(self, "禁止导出", "为防止覆盖原图，禁止导出到原图片所在文件夹")
                return

        # 开始导出
        success_count = 0
        fail_count = 0
        fail_files = []

        for img_path in self.imported_images:
            try:
                # 打开原图
                with Image.open(img_path).convert("RGBA") as img:
                    # 创建水印
                    watermark_layer = self.create_watermark_layer(img.size)
                    watermarked_img = Image.alpha_composite(img, watermark_layer)

                    # 处理缩放
                    resized_img = self.resize_image(watermarked_img)

                    # 确定输出格式
                    output_format, ext = self.get_output_format(img_path)

                    # 确定输出文件名
                    output_filename = self.get_output_filename(img_path, ext)
                    output_path = os.path.join(output_dir, output_filename)

                    # 保存图片
                    if output_format == "JPEG":
                        # JPEG不支持透明通道，转换为RGB
                        resized_img = resized_img.convert("RGB")
                        resized_img.save(output_path, "JPEG", quality=self.watermark_template["jpeg_quality"])
                    else:
                        resized_img.save(output_path, "PNG")

                    success_count += 1
            except Exception as e:
                fail_count += 1
                fail_files.append(f"{os.path.basename(img_path)}: {str(e)}")

        # 显示导出结果
        msg = f"导出完成！\n成功: {success_count} 张\n失败: {fail_count} 张"
        if fail_count > 0:
            msg += "\n失败文件：\n" + "\n".join(fail_files[:5])
            if len(fail_files) > 5:
                msg += f"\n... 还有 {len(fail_files) - 5} 个文件"

        QMessageBox.information(self, "导出结果", msg)

    def resize_image(self, img):
        """根据设置调整图片大小"""
        mode = self.watermark_template["resize_mode"]
        if mode == "none":
            return img

        width, height = img.size

        try:
            if mode == "width":
                new_width = int(self.watermark_template["resize_value"])
                ratio = new_width / width
                new_height = int(height * ratio)
            elif mode == "height":
                new_height = int(self.watermark_template["resize_value"])
                ratio = new_height / height
                new_width = int(width * ratio)
            elif mode == "percent":
                percent = self.watermark_template["resize_value"] / 100
                new_width = int(width * percent)
                new_height = int(height * percent)
            else:
                return img

            return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        except:
            return img

    def get_output_format(self, img_path):
        """确定输出格式和扩展名"""
        format_setting = self.watermark_template["output_format"]

        if format_setting == "same_as_input":
            # 使用原图格式
            ext = os.path.splitext(img_path)[1].lower()
            if ext in (".jpg", ".jpeg"):
                return "JPEG", ".jpg"
            else:
                return "PNG", ".png"
        elif format_setting == "JPEG":
            return "JPEG", ".jpg"
        else:
            return "PNG", ".png"

    def get_output_filename(self, img_path, ext):
        """确定输出文件名"""
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        rule_index = self.name_rule_combo.currentIndex()

        if rule_index == 0:  # 保留原文件名
            return f"{base_name}{ext}"
        elif rule_index == 1:  # 添加自定义前缀
            prefix = self.prefix_edit.text()
            return f"{prefix}{base_name}{ext}"
        else:  # 添加自定义后缀
            suffix = self.suffix_edit.text()
            return f"{base_name}{suffix}{ext}"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WatermarkTool()
    window.show()
    sys.exit(app.exec_())
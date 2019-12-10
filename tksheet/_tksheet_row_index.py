from ._tksheet_vars import *
from ._tksheet_other_classes import *

from collections import defaultdict, deque
from itertools import islice, repeat, accumulate, chain
from math import floor, ceil
from tkinter import ttk
import bisect
import csv as csv_module
import io
import pickle
import re
import tkinter as tk
import zlib
# for mac bindings
from platform import system as get_os


class RowIndex(tk.Canvas):
    def __init__(self,
                 parentframe = None,
                 main_canvas = None,
                 header_canvas = None,
                 max_rh = None,
                 max_row_width = None,
                 row_index_align = None,
                 row_index_width = None,
                 row_index_background = None,
                 row_index_border_color = None,
                 row_index_grid_color = None,
                 row_index_foreground = None,
                 row_index_select_background = None,
                 row_index_select_foreground = None,
                 drag_and_drop_color = None,
                 resizing_line_color = None):
        tk.Canvas.__init__(self,
                           parentframe,
                           height = None,
                           background = row_index_background,
                           highlightthickness = 0)
        self.parentframe = parentframe
        self.extra_motion_func = None
        self.extra_b1_press_func = None
        self.extra_b1_motion_func = None
        self.extra_b1_release_func = None
        self.selection_binding_func = None
        self.drag_selection_binding_func = None
        self.ri_extra_drag_drop_func = None
        self.extra_double_b1_func = None
        self.new_row_width = 0
        if row_index_width is None:
            self.set_width(100)
            self.default_width = 100
        else:
            self.set_width(row_index_width)
            self.default_width = row_index_width
        self.max_rh = float(max_rh)
        self.max_row_width = float(max_row_width)
        self.MT = main_canvas         # is set from within MainTable() __init__
        self.CH = header_canvas      # is set from within MainTable() __init__
        self.TL = None                # is set from within TopLeftRectangle() __init__
        self.text_color = row_index_foreground
        self.grid_color = row_index_grid_color
        self.row_index_border_color = row_index_border_color
        self.selected_cells_background = row_index_select_background
        self.selected_cells_foreground = row_index_select_foreground
        self.row_index_background = row_index_background
        self.drag_and_drop_color = drag_and_drop_color
        self.resizing_line_color = resizing_line_color
        self.align = row_index_align
        self.highlighted_cells = {}
        self.drag_and_drop_enabled = False
        self.dragged_row = None
        self.width_resizing_enabled = False
        self.height_resizing_enabled = False
        self.double_click_resizing_enabled = False
        self.row_selection_enabled = False
        self.rc_insert_row_enabled = False
        self.rc_delete_row_enabled = False
        self.visible_row_dividers = []
        self.row_width_resize_bbox = tuple()
        self.rsz_w = None
        self.rsz_h = None
        self.currently_resizing_width = False
        self.currently_resizing_height = False
        self.bind("<Motion>", self.mouse_motion)
        self.bind("<ButtonPress-1>", self.b1_press)
        self.bind("<Shift-ButtonPress-1>",self.shift_b1_press)
        self.bind("<B1-Motion>", self.b1_motion)
        self.bind("<ButtonRelease-1>", self.b1_release)
        self.bind("<Double-Button-1>", self.double_b1)
        self.bind("<MouseWheel>", self.mousewheel)

    def basic_bindings(self, onoff = "enable"):
        if onoff == "enable":
            self.bind("<Motion>", self.mouse_motion)
            self.bind("<ButtonPress-1>", self.b1_press)
            self.bind("<B1-Motion>", self.b1_motion)
            self.bind("<ButtonRelease-1>", self.b1_release)
            self.bind("<Double-Button-1>", self.double_b1)
            self.bind("<MouseWheel>", self.mousewheel)
        elif onoff == "disable":
            self.unbind("<Motion>")
            self.unbind("<ButtonPress-1>")
            self.unbind("<B1-Motion>")
            self.unbind("<ButtonRelease-1>")
            self.unbind("<Double-Button-1>")
            self.unbind("<MouseWheel>")

    def mousewheel(self, event = None):
        if event.num == 5 or event.delta == -120:
            self.yview_scroll(1, "units")
            self.MT.yview_scroll(1, "units")
        if event.num == 4 or event.delta == 120:
            if self.canvasy(0) <= 0:
                return
            self.yview_scroll( - 1, "units")
            self.MT.yview_scroll( - 1, "units")
        self.MT.main_table_redraw_grid_and_text(redraw_row_index = True)

    def set_width(self, new_width, set_TL = False):
        self.current_width = new_width
        self.config(width = new_width)
        if set_TL:
            self.TL.set_dimensions(new_w = new_width)

    def enable_bindings(self, binding):
        if binding == "row_width_resize":
            self.width_resizing_enabled = True
        elif binding == "row_height_resize":
            self.height_resizing_enabled = True
        elif binding == "double_click_row_resize":
            self.double_click_resizing_enabled = True
        elif binding == "row_select":
            self.row_selection_enabled = True
        elif binding == "drag_and_drop":
            self.drag_and_drop_enabled = True
        elif binding == "rc_delete_row":
            self.rc_delete_row_enabled = True
            self.ri_rc_popup_menu.entryconfig("Delete Rows", state = "normal")
        elif binding == "rc_insert_row":
            self.rc_insert_row_enabled = True
            self.ri_rc_popup_menu.entryconfig("Insert Row", state = "normal")
        
    def disable_bindings(self, binding):
        if binding == "row_width_resize":
            self.width_resizing_enabled = False
        elif binding == "row_height_resize":
            self.height_resizing_enabled = False
        elif binding == "double_click_row_resize":
            self.double_click_resizing_enabled = False
        elif binding == "row_select":
            self.row_selection_enabled = False
        elif binding == "drag_and_drop":
            self.drag_and_drop_enabled = False
        elif binding == "rc_delete_row":
            self.rc_delete_row_enabled = False
            self.ri_rc_popup_menu.entryconfig("Delete Rows", state = "disabled")
        elif binding == "rc_insert_row":
            self.rc_delete_row_enabled = False
            self.ri_rc_popup_menu.entryconfig("Insert Row", state = "disabled")

    def check_mouse_position_height_resizers(self, x, y):
        ov = None
        for x1, y1, x2, y2 in self.visible_row_dividers:
            if x >= x1 and y >= y1 and x <= x2 and y <= y2:
                ov = self.find_overlapping(x1, y1, x2, y2)
                break
        return ov

    def shift_b1_press(self, event):
        y = event.y
        r = self.MT.identify_row(y = y)
        if self.drag_and_drop_enabled or self.row_selection_enabled and self.rsz_h is None and self.rsz_w is None:
            if r < len(self.MT.row_positions) - 1:
                if r not in self.MT.selected_rows and self.row_selection_enabled:
                    r = int(r)
                    if self.MT.currently_selected and self.MT.currently_selected[0] == "row":
                        min_r = int(self.MT.currently_selected[1])
                        self.MT.selected_cols = set()
                        self.MT.selected_rows = set()
                        self.MT.sel_R = defaultdict(int)
                        self.MT.sel_C = defaultdict(int)
                        if r > min_r:
                            for i in range(min_r, r + 1):
                                self.MT.selected_rows.add(i)
                        elif r < min_r:
                            for i in range(r, min_r + 1):
                                self.MT.selected_rows.add(i)
                    else:
                        self.select_row(r)
                    self.MT.main_table_redraw_grid_and_text(redraw_header = True, redraw_row_index = True)
                    if self.selection_binding_func is not None:
                        self.selection_binding_func(("row", r))
                elif r in self.MT.selected_rows:
                    self.dragged_row = r

    def rc(self, event):
        self.focus_set()
        if self.MT.identify_row(y = event.y, allow_end = False) is None:
            self.MT.deselect("all")
            self.ri_rc_popup_menu.tk_popup(event.x_root, event.y_root)
        elif self.row_selection_enabled and all(v is None for v in (self.CH.rsz_h, self.CH.rsz_w, self.rsz_h, self.rsz_w)):
            r = self.MT.identify_row(y = event.y)
            if r < len(self.MT.row_positions) - 1:
                rows_selected = self.MT.anything_selected(exclude_columns = True, exclude_cells = True)
                if rows_selected:
                    y1 = self.MT.get_min_selected_cell_y()
                    y2 = self.MT.get_max_selected_cell_y()
                else:
                    y1 = None
                    y2 = None
                if all(e is not None for e in (y1, y2)) and r >= y1 and r <= y2:
                    self.ri_rc_popup_menu.tk_popup(event.x_root, event.y_root)
                else:
                    self.select_row(r, redraw = True)
                    self.ri_rc_popup_menu.tk_popup(event.x_root, event.y_root)

    def mouse_motion(self, event):
        if not self.currently_resizing_height and not self.currently_resizing_width:
            x = self.canvasx(event.x)
            y = self.canvasy(event.y)
            mouse_over_resize = False
            if self.height_resizing_enabled and not mouse_over_resize:
                ov = self.check_mouse_position_height_resizers(x, y)
                if ov is not None:
                    for itm in ov:
                        tgs = self.gettags(itm)
                        if "h" == tgs[0]:
                            break
                    r = int(tgs[1])
                    self.config(cursor = "sb_v_double_arrow")
                    self.rsz_h = r
                    mouse_over_resize = True
                else:
                    self.rsz_h = None
            if self.width_resizing_enabled and not mouse_over_resize:
                try:
                    x1, y1, x2, y2 = self.row_width_resize_bbox[0], self.row_width_resize_bbox[1], self.row_width_resize_bbox[2], self.row_width_resize_bbox[3]
                    if x >= x1 and y >= y1 and x <= x2 and y <= y2:
                        self.config(cursor = "sb_h_double_arrow")
                        self.rsz_w = True
                        mouse_over_resize = True
                    else:
                        self.rsz_w = None
                except:
                    self.rsz_w = None
            if not mouse_over_resize:
                self.MT.reset_mouse_motion_creations()
        if self.extra_motion_func is not None:
            self.extra_motion_func(event)
        
    def b1_press(self, event = None):
        self.focus_set()
        self.MT.unbind("<MouseWheel>")
        x = self.canvasx(event.x)
        y = self.canvasy(event.y)
        if self.check_mouse_position_height_resizers(x, y) is None:
            self.rsz_h = None
        if not x >= self.row_width_resize_bbox[0] and y >= self.row_width_resize_bbox[1] and x <= self.row_width_resize_bbox[2] and y <= self.row_width_resize_bbox[3]:
            self.rsz_w = None
        if self.height_resizing_enabled and self.rsz_h is not None:
            self.currently_resizing_height = True
            y = self.MT.row_positions[self.rsz_h]
            line2y = self.MT.row_positions[self.rsz_h - 1]
            x1, y1, x2, y2 = self.MT.get_canvas_visible_area()
            self.create_line(0, y, self.current_width, y, width = 1, fill = self.resizing_line_color, tag = "rhl")
            self.MT.create_line(x1, y, x2, y, width = 1, fill = self.resizing_line_color, tag = "rhl")
            self.create_line(0, line2y, self.current_width, line2y, width = 1, fill = self.resizing_line_color, tag = "rhl2")
            self.MT.create_line(x1, line2y, x2, line2y, width = 1, fill = self.resizing_line_color, tag = "rhl2")
        elif self.width_resizing_enabled and self.rsz_h is None and self.rsz_w == True:
            self.currently_resizing_width = True
            x1, y1, x2, y2 = self.MT.get_canvas_visible_area()
            x = int(event.x)
            if x < self.MT.min_cw:
                x = int(self.MT.min_cw)
            self.new_row_width = x
            self.create_line(x, y1, x, y2, width = 1, fill = self.resizing_line_color, tag = "rwl")
        elif self.MT.identify_row(y = event.y, allow_end = False) is None:
            self.MT.deselect("all")
        elif self.row_selection_enabled and self.rsz_h is None and self.rsz_w is None:
            r = self.MT.identify_row(y = event.y)
            if r < len(self.MT.row_positions) - 1:
                self.select_row(r, redraw = True)
        if self.extra_b1_press_func is not None:
            self.extra_b1_press_func(event)
    
    def b1_motion(self, event):
        x1,y1,x2,y2 = self.MT.get_canvas_visible_area()
        if self.height_resizing_enabled and self.rsz_h is not None and self.currently_resizing_height:
            y = self.canvasy(event.y)
            size = y - self.MT.row_positions[self.rsz_h - 1]
            if not size <= self.MT.min_rh and size < self.max_rh:
                self.delete("rhl")
                self.MT.delete("rhl")
                self.create_line(0, y, self.current_width, y, width = 1, fill = self.resizing_line_color, tag = "rhl")
                self.MT.create_line(x1, y, x2, y, width = 1, fill = self.resizing_line_color, tag = "rhl")
        elif self.width_resizing_enabled and self.rsz_w is not None and self.currently_resizing_width:
            evx = event.x
            self.delete("rwl")
            self.MT.delete("rwl")
            if evx > self.current_width:
                x = self.MT.canvasx(evx - self.current_width)
                if evx > self.max_row_width:
                    evx = int(self.max_row_width)
                    x = self.MT.canvasx(evx - self.current_width)
                self.new_row_width = evx
                self.MT.create_line(x, y1, x, y2, width = 1, fill = self.resizing_line_color, tag = "rwl")
            else:
                x = evx
                if x < self.MT.min_cw:
                    x = int(self.MT.min_cw)
                self.new_row_width = x
                self.create_line(x, y1, x, y2, width = 1, fill = self.resizing_line_color, tag = "rwl")
        if self.drag_and_drop_enabled and self.row_selection_enabled and self.rsz_h is None and self.rsz_w is None and self.dragged_row is not None and self.MT.selected_rows:
            y = self.canvasy(event.y)
            if y > 0 and y < self.MT.row_positions[-1]:
                y = event.y
                hend = self.winfo_height()
                if y >= hend - 0:
                    end_row = bisect.bisect_right(self.MT.row_positions, self.canvasy(hend))
                    end_row -= 1
                    if not end_row == len(self.MT.row_positions) - 1:
                        try:
                            self.MT.see(r = end_row, c = 0, keep_yscroll = False, keep_xscroll = True, bottom_right_corner = False, check_cell_visibility = True)
                        except:
                            pass
                elif y <= 0:
                    start_row = bisect.bisect_left(self.MT.row_positions, self.canvasy(0))
                    if y <= -40:
                        start_row -= 3
                    else:
                        start_row -= 2
                    if start_row <= 0:
                        start_row = 0
                    try:
                        self.MT.see(r = start_row, c = 0, keep_yscroll = False, keep_xscroll = True, bottom_right_corner = False, check_cell_visibility = True)
                    except:
                        pass
                rectw = self.MT.row_positions[max(self.MT.selected_rows) + 1] - self.MT.row_positions[min(self.MT.selected_rows)]
                start = self.canvasy(event.y - int(rectw / 2))
                end = self.canvasy(event.y + int(rectw / 2))
                self.delete("dd")
                self.create_rectangle(0, start, self.current_width - 1, end, fill = self.drag_and_drop_color, outline = self.grid_color, tag = "dd")
                self.tag_raise("dd")
                self.tag_raise("t")
                self.tag_raise("h")
        elif self.MT.drag_selection_enabled and self.row_selection_enabled and self.rsz_h is None and self.rsz_w is None:
            end_row = self.MT.identify_row(y = event.y)
            if end_row < len(self.MT.row_positions) - 1 and len(self.MT.currently_selected) == 2:
                if self.MT.currently_selected[0] == "row":
                    start_row = self.MT.currently_selected[1]
                    self.MT.selected_cols = set()
                    self.MT.selected_rows = set()
                    self.MT.sel_R = defaultdict(int)
                    self.MT.sel_C = defaultdict(int)
                    if end_row >= start_row:
                        for r in range(start_row, end_row + 1):
                            self.MT.selected_rows.add(r)
                    elif end_row < start_row:
                        for r in range(end_row, start_row + 1):
                            self.MT.selected_rows.add(r)
                    if self.drag_selection_binding_func is not None:
                        self.drag_selection_binding_func(("rows", sorted([start_row, end_row])))
            if event.y > self.winfo_height():
                try:
                    self.MT.yview_scroll(1, "units")
                    self.yview_scroll(1, "units")
                except:
                    pass
            elif event.y < 0 and self.canvasy(self.winfo_height()) > 0:
                try:
                    self.yview_scroll(-1, "units")
                    self.MT.yview_scroll(-1, "units")
                except:
                    pass
            self.MT.main_table_redraw_grid_and_text(redraw_header = False, redraw_row_index = True)
        if self.extra_b1_motion_func is not None:
            self.extra_b1_motion_func(event)
            
    def b1_release(self, event = None):
        self.MT.bind("<MouseWheel>", self.MT.mousewheel)
        if self.height_resizing_enabled and self.rsz_h is not None and self.currently_resizing_height:
            self.currently_resizing_height = False
            new_row_pos = self.coords("rhl")[1]
            self.delete("rhl", "rhl2")
            self.MT.delete("rhl", "rhl2")
            size = new_row_pos - self.MT.row_positions[self.rsz_h - 1]
            if size < self.MT.min_rh:
                new_row_pos = ceil(self.MT.row_positions[self.rsz_h - 1] + self.MT.min_rh)
            elif size > self.max_rh:
                new_row_pos = floor(self.MT.row_positions[self.rsz_h - 1] + self.max_rh)
            increment = new_row_pos - self.MT.row_positions[self.rsz_h]
            self.MT.row_positions[self.rsz_h + 1:] = [e + increment for e in islice(self.MT.row_positions, self.rsz_h + 1, len(self.MT.row_positions))]
            self.MT.row_positions[self.rsz_h] = new_row_pos
            self.MT.main_table_redraw_grid_and_text(redraw_header = True, redraw_row_index = True)
        elif self.width_resizing_enabled and self.rsz_w is not None and self.currently_resizing_width:
            self.currently_resizing_width = False
            self.delete("rwl")
            self.MT.delete("rwl")
            self.set_width(self.new_row_width, set_TL = True)
            self.MT.main_table_redraw_grid_and_text(redraw_header = True, redraw_row_index = True)
        if self.drag_and_drop_enabled and self.MT.selected_rows and self.row_selection_enabled and self.rsz_h is None and self.rsz_w is None and self.dragged_row is not None:
            self.delete("dd")
            y = event.y
            r = self.MT.identify_row(y = y)
            if r != self.dragged_row and r is not None and len(self.MT.selected_rows) != (len(self.MT.row_positions) - 1):
                rowsiter = list(self.MT.selected_rows)
                rowsiter.sort()
                stins = rowsiter[0]
                endins = rowsiter[-1] + 1
                if self.dragged_row < r and r >= len(self.MT.row_positions) - 1:
                    r -= 1
                r_ = int(r)
                if r >= endins:
                    r += 1
                if self.ri_extra_drag_drop_func is not None:
                    self.ri_extra_drag_drop_func(self.MT.selected_rows, int(r_))
                else:
                    if stins > r:
                        self.MT.data_ref[r:r] = self.MT.data_ref[stins:endins]
                        self.MT.data_ref[stins + len(rowsiter):endins + len(rowsiter)] = []
                        if not isinstance(self.MT.my_row_index, int) and self.MT.my_row_index:
                            try:
                                self.MT.my_row_index[r:r] = self.MT.my_row_index[stins:endins]
                                self.MT.my_row_index[stins + len(rowsiter):endins + len(rowsiter)] = []
                            except:
                                pass
                    else:
                        self.MT.data_ref[r:r] = self.MT.data_ref[stins:endins]
                        self.MT.data_ref[stins:endins] = []
                        if not isinstance(self.MT.my_row_index, int) and self.MT.my_row_index:
                            try:
                                self.MT.my_row_index[r:r] = self.MT.my_row_index[stins:endins]
                                self.MT.my_row_index[stins:endins] = []
                            except:
                                pass
                rhs = self.MT.parentframe.get_row_heights()
                if stins > r:
                    rhs[r:r] = rhs[stins:endins]
                    rhs[stins + len(rowsiter):endins + len(rowsiter)] = []
                else:
                    rhs[r:r] = rhs[stins:endins]
                    rhs[stins:endins] = []
                self.MT.parentframe.set_row_heights(rhs)
                if (r_ - 1) + len(rowsiter) > len(self.MT.row_positions) - 1:
                    sels_start = len(self.MT.row_positions) - 1 - len(rowsiter)
                    newrowidxs = tuple(range(sels_start, len(self.MT.row_positions) - 1))
                else:
                    if r_ > endins:
                        r_ += 1
                        sels_start = r_ - len(rowsiter)
                    else:
                        if r_ == endins and len(rowsiter) == 1:
                            pass
                        else:
                            if r_ > endins:
                                r_ += 1
                            if r_ == endins:
                                r_ -= 1
                            if r_ < 0:
                                r_ = 0
                        sels_start = r_
                    newrowidxs = tuple(range(sels_start, sels_start + len(rowsiter)))
                self.MT.selected_cols = set()
                self.MT.selected_rows = set()
                self.MT.sel_R = defaultdict(int)
                self.MT.sel_C = defaultdict(int)
                for rowsel in newrowidxs:
                    self.MT.selected_rows.add(rowsel)
                self.MT.undo_storage = deque(maxlen = 20)
                self.MT.main_table_redraw_grid_and_text(redraw_header = True, redraw_row_index = True)
        self.dragged_row = None
        self.currently_resizing_width = False
        self.currently_resizing_height = False
        self.rsz_w = None
        self.rsz_h = None
        self.mouse_motion(event)
        if self.extra_b1_release_func is not None:
            self.extra_b1_release_func(event)

    def double_b1(self, event = None):
        self.focus_set()
        if self.double_click_resizing_enabled and self.height_resizing_enabled and self.rsz_h is not None and not self.currently_resizing_height:
            row = self.rsz_h - 1
            self.set_row_height(row)
            self.MT.main_table_redraw_grid_and_text(redraw_header = True, redraw_row_index = True)
        elif self.row_selection_enabled and self.rsz_h is None and self.rsz_w is None:
            r = self.MT.identify_row(y = event.y)
            if r < len(self.MT.row_positions) - 1:
                self.select_row(r, redraw = True)
        self.mouse_motion(event)
        self.rsz_h = None
        if self.extra_double_b1_func is not None:
            self.extra_double_b1_func(event)

    def set_row_height(self, row, new_height = None, only_set_if_too_small = False):
        r_norm = row + 1
        r_extra = row + 2
        if new_height is None:
            try:
                new_height = self.GetLinesHeight(max((cll for cll in self.MT.data_ref[row]), key = self.GetNumLines))
            except:
                new_height = int(self.MT.min_rh)
        if new_height < self.MT.min_rh:
            new_height = int(self.MT.min_rh)
        elif new_height > self.max_rh:
            new_height = int(self.max_rh)
        if only_set_if_too_small:
            if new_height <= self.MT.row_positions[row + 1] - self.MT.row_positions[row]:
                return
        new_row_pos = self.MT.row_positions[row] + new_height
        increment = new_row_pos - self.MT.row_positions[r_norm]
        self.MT.row_positions[r_extra:] = [e + increment for e in islice(self.MT.row_positions, r_extra, len(self.MT.row_positions))]
        self.MT.row_positions[r_norm] = new_row_pos

    def GetNumLines(self, cll):
        return len(cll.split("\n"))

    def GetLinesHeight(self, cll):
        lns = cll.split("\n")
        if len(lns) > 1:
            y = self.MT.fl_ins
            for i in range(len(lns)):
                y += self.MT.xtra_lines_increment
        else:
            y = int(self.MT.min_rh)
        return y

    def highlight_cells(self, r = 0, cells = tuple(), bg = None, fg = None, redraw = False):
        if bg is None and fg is None:
            return
        if cells:
            self.highlighted_cells = {r_: (bg, fg)  for r_ in cells}
        else:
            self.highlighted_cells[r] = (bg, fg)
        if redraw:
            self.MT.main_table_redraw_grid_and_text(False, True)

    def add_selection(self, r, redraw = False, run_binding_func = True, set_as_current = True):
        r = int(r)
        if set_as_current:
            self.MT.currently_selected = ("row", r)
        self.MT.selected_rows.add(r)
        self.MT.selected_cols = set()
        self.MT.selection_boxes = set()
        self.MT.sel_R = defaultdict(int)
        self.MT.sel_C = defaultdict(int)
        if redraw:
            self.MT.main_table_redraw_grid_and_text(redraw_header = True, redraw_row_index = True)
        if self.selection_binding_func is not None and run_binding_func:
            self.selection_binding_func(("row", r))

    def select_row(self, r, redraw = False, keep_other_selections = False):
        r = int(r)
        ignore_keep = False
        if keep_other_selections:
            if r in self.MT.selected_rows:
                self.MT.currently_selected = ("row", r)
            else:
                ignore_keep = True
        if ignore_keep or not keep_other_selections:
            self.MT.currently_selected = ("row", r)
            self.MT.selected_rows = {r}
        self.MT.selected_cols = set()
        self.MT.selection_boxes = set()
        self.MT.sel_R = defaultdict(int)
        self.MT.sel_C = defaultdict(int)
        if redraw:
            self.MT.main_table_redraw_grid_and_text(redraw_header = True, redraw_row_index = True)
        if self.selection_binding_func is not None:
            self.selection_binding_func(("row", r))

    def redraw_grid_and_text(self, last_row_line_pos, y1, y_stop, start_row, end_row, y2, x1, x_stop):
        try:
            self.configure(scrollregion = (0, 0, self.current_width, last_row_line_pos + 100))
            self.delete("fh", "h", "v", "t", "s")
            self.visible_row_dividers = []
            y = self.MT.row_positions[start_row]
            self.create_line(0, y, self.current_width, y, fill = self.grid_color, width = 1, tag = "fh")
            xend = self.current_width - 6
            self.row_width_resize_bbox = (self.current_width - 5, y1, self.current_width, y2)
            if self.height_resizing_enabled:
                for r in range(start_row + 1,end_row):
                    y = self.MT.row_positions[r]
                    self.visible_row_dividers.append((1, y - 4, xend, y + 4))
                    self.create_line(0, y, self.current_width, y, fill = self.grid_color, width = 1, tag = ("h", f"{r}"))
            else:
                for r in range(start_row + 1,end_row):
                    y = self.MT.row_positions[r]
                    self.create_line(0, y, self.current_width, y, fill = self.grid_color, width = 1, tag = ("h", f"{r}"))
            sb = y2 + 2
            c_2 = self.selected_cells_background if self.selected_cells_background.startswith("#") else Color_Map_[self.selected_cells_background]
            if self.align == "center":
                mw = self.current_width - 7
                x = floor(mw / 2)
                for r in range(start_row, end_row - 1):
                    fr = self.MT.row_positions[r]
                    sr = self.MT.row_positions[r+1]
                    if sr > sb:
                        sr = sb
                    if r in self.highlighted_cells and (r in self.MT.sel_R or r in self.MT.selected_rows):
                        c_1 = self.highlighted_cells[r][0] if self.highlighted_cells[r][0].startswith("#") else Color_Map_[self.highlighted_cells[r][0]]
                        self.create_rectangle(0,
                                              fr + 1,
                                              self.current_width - 1,
                                              sr,
                                              fill = (f"#{int((int(c_1[1:3], 16) + int(c_2[1:3], 16)) / 2):02X}" +
                                                      f"{int((int(c_1[3:5], 16) + int(c_2[3:5], 16)) / 2):02X}" +
                                                      f"{int((int(c_1[5:], 16) + int(c_2[5:], 16)) / 2):02X}"),
                                              outline = "",
                                              tag = "s")
                        tf = self.selected_cells_foreground if self.highlighted_cells[r][1] is None else self.highlighted_cells[r][1]
                    elif (r in self.MT.sel_R or r in self.MT.selected_rows):
                        self.create_rectangle(0, fr + 1, self.current_width - 1, sr, fill = self.selected_cells_background, outline = "", tag = "s")
                        tf = self.selected_cells_foreground
                    elif r in self.highlighted_cells:
                        self.create_rectangle(0, fr + 1, self.current_width - 1, sr, fill = self.highlighted_cells[r][0], outline = "", tag = "s")
                        tf = self.text_color if self.highlighted_cells[r][1] is None else self.highlighted_cells[r][1]
                    else:
                        tf = self.text_color
                    if isinstance(self.MT.my_row_index, int):
                        lns = self.MT.data_ref[r][self.MT.my_row_index].split("\n")
                    else:
                        try:
                            lns = self.MT.my_row_index[r].split("\n")
                        except:
                            lns = (f"{r + 1}", )
                    fl = lns[0]
                    y = fr + self.MT.fl_ins
                    if y + self.MT.half_txt_h > y1:
                        t = self.create_text(x, y, text = fl, fill = tf, font = self.MT.my_font, anchor = "center", tag = "t")
                        wd = self.bbox(t)
                        wd = wd[2] - wd[0]
                        if wd > mw:
                            tl = len(fl)
                            slce = tl - floor(tl * (mw / wd))
                            if slce % 2:
                                slce += 1
                            else:
                                slce += 2
                            slce = int(slce / 2)
                            fl = fl[slce:tl - slce]
                            self.itemconfig(t, text = fl)
                            wd = self.bbox(t)
                            while wd[2] - wd[0] > mw:
                                fl = fl[1: - 1]
                                self.itemconfig(t, text = fl)
                                wd = self.bbox(t)
                    if len(lns) > 1:
                        stl = int((y1 - y) / self.MT.xtra_lines_increment) - 1
                        if stl < 1:
                            stl = 1
                        y += (stl * self.MT.xtra_lines_increment)
                        if y + self.MT.half_txt_h < sr:
                            for i in range(stl,len(lns)):
                                txt = lns[i]
                                t = self.create_text(x, y, text = txt, fill = tf, font = self.MT.my_font, anchor = "center", tag = "t")
                                wd = self.bbox(t)
                                wd = wd[2] - wd[0]
                                if wd > mw:
                                    tl = len(txt)
                                    slce = tl - floor(tl * (mw / wd))
                                    if slce % 2:
                                        slce += 1
                                    else:
                                        slce += 2
                                    slce = int(slce / 2)
                                    txt = txt[slce:tl - slce]
                                    self.itemconfig(t, text = txt)
                                    wd = self.bbox(t)
                                    while wd[2] - wd[0] > mw:
                                        txt = txt[1: - 1]
                                        self.itemconfig(t, text = txt)
                                        wd = self.bbox(t)
                                y += self.MT.xtra_lines_increment
                                if y + self.MT.half_txt_h > sr:
                                    break
            elif self.align == "w":
                mw = self.current_width - 7
                x = 7
                for r in range(start_row,end_row - 1):
                    fr = self.MT.row_positions[r]
                    sr = self.MT.row_positions[r + 1]
                    if sr > sb:
                        sr = sb
                    if r in self.highlighted_cells and (r in self.MT.sel_R or r in self.MT.selected_rows):
                        c_1 = self.highlighted_cells[r][0] if self.highlighted_cells[r][0].startswith("#") else Color_Map_[self.highlighted_cells[r][0]]
                        self.create_rectangle(0,
                                              fr + 1,
                                              self.current_width - 1,
                                              sr,
                                              fill = (f"#{int((int(c_1[1:3], 16) + int(c_2[1:3], 16)) / 2):02X}" +
                                                      f"{int((int(c_1[3:5], 16) + int(c_2[3:5], 16)) / 2):02X}" +
                                                      f"{int((int(c_1[5:], 16) + int(c_2[5:], 16)) / 2):02X}"),
                                              outline = "",
                                              tag = "s")
                        tf = self.selected_cells_foreground if self.highlighted_cells[r][1] is None else self.highlighted_cells[r][1]
                    elif (r in self.MT.sel_R or r in self.MT.selected_rows):
                        self.create_rectangle(0, fr + 1, self.current_width - 1, sr, fill = self.selected_cells_background, outline = "", tag = "s")
                        tf = self.selected_cells_foreground
                    elif r in self.highlighted_cells:
                        self.create_rectangle(0, fr + 1, self.current_width - 1, sr, fill = self.highlighted_cells[r][0], outline = "", tag = "s")
                        tf = self.text_color if self.highlighted_cells[r][1] is None else self.highlighted_cells[r][1]
                    else:
                        tf = self.text_color
                    if isinstance(self.MT.my_row_index, int):
                        lns = self.MT.data_ref[r][self.MT.my_row_index].split("\n")
                    else:
                        try:
                            lns = self.MT.my_row_index[r].split("\n")
                        except:
                            lns = (f"{r + 1}", )
                    y = fr + self.MT.fl_ins
                    if y + self.MT.half_txt_h > y1:
                        fl = lns[0]
                        t = self.create_text(x, y, text = fl, fill = tf, font = self.MT.my_font, anchor = "w", tag = "t")
                        wd = self.bbox(t)
                        wd = wd[2] - wd[0]
                        if wd > mw:
                            nl = int(len(fl) * (mw / wd)) - 1
                            self.itemconfig(t, text = fl[:nl])
                            wd = self.bbox(t)
                            while wd[2] - wd[0] > mw:
                                nl -= 1
                                self.dchars(t, nl)
                                wd = self.bbox(t)
                    if len(lns) > 1:
                        stl = int((y1 - y) / self.MT.xtra_lines_increment) - 1
                        if stl < 1:
                            stl = 1
                        y += (stl * self.MT.xtra_lines_increment)
                        if y + self.MT.half_txt_h < sr:
                            for i in range(stl, len(lns)):
                                txt = lns[i]
                                t = self.create_text(x, y, text = txt, fill = tf, font = self.MT.my_font, anchor = "w", tag = "t")
                                wd = self.bbox(t)
                                wd = wd[2] - wd[0]
                                if wd > mw:
                                    nl = int(len(txt) * (mw / wd)) - 1
                                    self.itemconfig(t, text = txt[:nl])
                                    wd = self.bbox(t)
                                    while wd[2] - wd[0] > mw:
                                        nl -= 1
                                        self.dchars(t, nl)
                                        wd = self.bbox(t)
                                y += self.MT.xtra_lines_increment
                                if y + self.MT.half_txt_h > sr:
                                    break
            self.create_line(self.current_width - 1, y1, self.current_width - 1, y_stop, fill = self.row_index_border_color, width = 1, tag = "v")
        except:
            return

    def GetCellCoords(self, event = None, r = None, c = None):
        pass

    
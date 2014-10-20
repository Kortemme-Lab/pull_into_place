#!/usr/bin/env python2
# encoding: utf-8

"""\
Display score vs distance plots for sets of models generated during the design 
pipeline.  In particular, this script can be used to visualize results from 
both the model building and design validation stages of the pipeline.  Often 
you would use this script to get a big-picture view of your designs before 
deciding which are worth carrying forward.

Usage: view_models.py [options] <directories>...

Options:
    -f, --force
        Force the cache to be regenerated.

    -q, --quiet
        Build the cache, but don't launch the GUI.

    -r PATH, --restraints PATH
        Specify a restraints file to use while building the cache.

    -i, --interesting
        Hide uninteresting groups by default.

    -x XLIM, --xlim XLIM
        Set the x-axis limit for all distance metrics.
"""

# Imports (fold)
import collections
import docopt
import glob
import gtk
import matplotlib
import matplotlib.pyplot
import os
import pango
import re
import shutil
import yaml

from numpy import *
from biophysics import pdb
from matplotlib.figure import Figure
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg
from matplotlib.backends.backend_gtkagg import NavigationToolbar2GTKAgg


class ModelGroup (object):

    def __init__(self, directory, restraints=None, use_cache=True):
        self.directory = directory
        self.notes_path = os.path.join(directory, 'notes.txt')
        self.interest_path = os.path.join(directory, 'interesting')
        self.rep_path = os.path.join(directory, 'representative.txt')

        self.structures = None
        self._notes = ""
        self._interesting = False
        self._representative = None

        self._load_annotations()
        self._load_scores_and_dists(restraints, use_cache)

    def __str__(self):
        return '<ModelGroup dir={}>'.format(self.directory)

    def __len__(self):
        return len(self.paths)


    @property
    def paths(self):
        return self.structures['path']

    @property
    def notes(self):
        return self._notes

    @notes.setter
    def set_notes(self, notes):
        self._notes = notes
        self._save_notes()

    @property
    def interest(self):
        return self._interest

    def set_interest(self, interest):
        self._interest = interest
        self._save_interest()

    @property
    def representative(self):
        if self._representative is None:
            return argmin(self.get_scores('Total Score'))
        else:
            return self._representative

    @representative.setter
    def set_representative(self, index):
        self._representative = index
        self._save_representative()

    @property
    def representative_path(self):
        return self.paths[self.representative]

    def get_scores(self, metric):
        if metric == 'Total Score':
            return self.structures['total_score']
        elif metric == 'Dunbrack Score':
            return self.structures['dunbrack_score']
        elif metric == 'Buried Unsat Score':
            return self.structures['buried_unsat_score']
        else:
            raise ValueError, "Unknown score '{}'.".format(metric)

    def get_distances(self, metric):
        if metric == 'Loop RMSD':
            return self.structures['loop_dist']
        elif metric == 'Restraint Dist':
            return self.structures['restraint_dist']
        else:
            raise ValueError, "Unknown distance metric '{}'.".format(metric)


    def _load_annotations(self):
        try:
            with open(self.notes_path) as file:
                self._notes = file.read()
        except IOError:
            pass

        self._interest = os.path.exists(self.interest_path)

        try:
            with open(self.rep_path) as file:
                self._representative = int(file.read())
        except IOError:
            pass

    def _load_scores_and_dists(self, restraints, use_cache):
        from libraries import structures

        self.structures = structures.load(self.directory, restraints, use_cache)

    def _save_notes(self):
        with open(self.notes_path, 'w') as file:
            file.write(self.notes)

        if os.path.exists(self.notes_path) and not self.notes:
            os.remove(self.notes_path)

    def _save_interest(self):
        path_exists = os.path.exists(self.interest_path)

        if self.interest:
            if path_exists: pass
            else: open(self.interest_path, 'w').close()
        else:
            if path_exists: os.remove(self.interest_path)
            else: pass

    def _save_representative(self):
        if self._representative is not None:
            with open(self.rep_path, 'w') as file:
                file.write(str(self._representative))

        elif os.path.exists(self.rep_path):
            os.remove(self.rep_path)


class ModelView (gtk.Window):

    def __init__(self, groups, arguments):
        
        # Setup the parent class.

        gtk.Window.__init__(self)
        self.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.connect('key-press-event', self.on_hotkey_press)

        # Setup the data members.

        self.groups = groups
        self.keys = list()
        self.filter = 'all' if not arguments['--interesting'] else 'interesting'
        self.new_selection = None
        self.selected_decoy = None
        self.xlim = arguments.get('--xlim')
        if self.xlim is not None:
            self.xlim = float(self.xlim)

        self.distance_metrics = 'Restraint Dist', 'Loop RMSD'
        self.distance_metric = self.distance_metrics[0]
        self.score_metrics = 'Total Score', 'Dunbrack Score', 'Buried Unsat Score'
        self.score_metric = self.score_metrics[0]

        # Setup the GUI.

        self.connect('destroy', lambda x: gtk.main_quit())
        self.set_default_size(int(1.618 * 529), 529)

        model_viewer = self.setup_model_viewer()
        model_list = self.setup_model_list()
        menu_bar = self.setup_menu_bar()

        hbox = gtk.HBox()
        hbox.pack_start(model_list, expand=False, padding=3)
        hbox.pack_start(model_viewer, expand=True, padding=3)

        vbox = gtk.VBox()
        vbox.pack_start(menu_bar, expand=False)
        vbox.pack_start(hbox, expand=True, padding=3)

        self.add(vbox)
        self.update_everything()
        self.show_all()

    def get_interesting_groups(self):
        return [x for x in self.groups.values() if x.interest]

    def num_interesting_groups(self):
        count = 0
        for group in self.groups.values():
            count += 1 if group.interest else 0
        return count


    def setup_model_list(self):
        return self.setup_job_tree_view()

    def setup_model_viewer(self):
        plot = self.setup_score_vs_dist_plot()
        notes = self.setup_annotation_area()

        panes = gtk.VPaned()
        panes.add1(plot)
        panes.add2(notes)

        return panes

    def setup_menu_bar(self):
        # Create the file menu.

        file_config = [
                ("Save interesting paths",
                    lambda w: self.save_interesting_paths()),
                ("Save interesting funnels",
                    lambda w: self.save_interesting_funnels()),
                ("Save interesting pymol sessions",
                    lambda w: self.save_interesting_pymol_sessions()),
                (u"Save sub-0.6Å decoys",
                    lambda w: self.save_subangstrom_decoys()),
        ]
        file_submenu = gtk.Menu()

        for label, callback in file_config:
            item = gtk.MenuItem(label)
            item.connect('activate', callback)
            item.show()
            file_submenu.append(item)

        file_item = gtk.MenuItem("File")
        file_item.set_submenu(file_submenu)
        file_item.show()

        # Create the view menu.

        view_config = [
                "Show all groups", 
                "Show interesting groups",
                "Show interesting and annotated groups",
                "Show interesting and unannotated groups",
                "Show annotated groups",
                "Show uninteresting groups",
        ]
        view_submenu = gtk.Menu()

        def on_pick_filter(widget, filter):
            self.filter_by(filter)

        for label in view_config:
            filter = ' '.join(label.split()[1:-1])
            item = gtk.MenuItem(label)
            item.connect('activate', on_pick_filter, filter)
            item.show()
            view_submenu.append(item)

        view_item = gtk.MenuItem("View");
        view_item.set_submenu(view_submenu)
        view_item.show()

        # Create and return the menu bar.

        menu_bar = gtk.MenuBar()
        menu_bar.append(file_item)
        menu_bar.append(view_item)

        return menu_bar

    def setup_job_tree_view(self):
        list_store = gtk.ListStore(str)

        text = gtk.CellRendererText()
        icon = gtk.CellRendererPixbuf()

        self.view = gtk.TreeView(list_store)
        self.view.set_model(list_store)
        self.view.set_rubber_banding(True)
        self.view.set_enable_search(False)
        #self.view.set_size_request(200, -1)

        columns = [
                ('Name', 'directory'),
        ]

        for index, parameters in enumerate(columns):
            title, attr = parameters

            def cell_data_func(column, cell, model, iter, attr):
                key = model.get_value(iter, 0)
                group = self.groups[key]
                text = getattr(group, attr)
                weight = 700 if group.interest else 400

                cell.set_property('text', text)
                cell.set_property('weight', weight)

            def sort_func(model, iter_1, iter_2, attr):
                key_1 = model.get_value(iter_1, 0)
                key_2 = model.get_value(iter_2, 0)
                group_1 = self.groups[key_1]
                group_2 = self.groups[key_2]
                value_1 = getattr(group_1, attr)
                value_2 = getattr(group_2, attr)
                return cmp(value_1, value_2)

            list_store.set_sort_func(index, sort_func, attr);

            column = gtk.TreeViewColumn(title, text)
            column.set_cell_data_func(text, cell_data_func, attr)
            column.set_sort_column_id(index)
            self.view.append_column(column)

        selector = self.view.get_selection()
        selector.connect("changed", self.on_select_groups)
        selector.set_mode(gtk.SELECTION_MULTIPLE)

        scroller = gtk.ScrolledWindow()
        scroller.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroller.add(self.view)

        frame = gtk.Frame()
        frame.add(scroller)

        return frame

    def setup_score_vs_dist_plot(self):
        figure = Figure(facecolor='#edecea')

        self.axes = figure.add_axes((0.15, 0.15, 0.75, 0.75))
        self.axes.set_ylabel('Score')

        self.canvas = ModelCanvas(figure)
        self.canvas.mpl_connect('pick_event', self.on_select_decoy)
        self.canvas.mpl_connect('button_press_event', self.on_click_plot_mpl)
        self.canvas.connect('button-press-event', self.on_click_plot_gtk)
        self.canvas.set_size_request(-1, 350)

        axis_menu = gtk.Menu()

        self.axis_menu_items = {}
        self.axis_menu_handlers = []

        for metric in self.score_metrics + self.distance_metrics:
            menu_item = gtk.CheckMenuItem(metric)
            menu_item.set_draw_as_radio(True)
            menu_item.show()
            handler_id = menu_item.connect('toggled', self.on_change_metric)

            self.axis_menu_items[metric] = menu_item
            self.axis_menu_handlers.append((menu_item, handler_id))

        for metric in self.score_metrics:
            axis_menu.append(self.axis_menu_items[metric])

        separator = gtk.SeparatorMenuItem()
        separator.show()
        axis_menu.append(separator)

        for metric in self.distance_metrics:
            axis_menu.append(self.axis_menu_items[metric])

        self.toolbar = ModelToolbar(self.canvas, self, axis_menu)

        vbox = gtk.VBox()
        vbox.pack_start(self.canvas)
        vbox.pack_start(self.toolbar, expand=False)

        return vbox

    def setup_annotation_area(self):
        self.notes = gtk.TextView()
        self.notes.set_wrap_mode(gtk.WRAP_WORD)
        self.notes.set_size_request(-1, 100)
        self.notes.set_left_margin(3)
        self.notes.set_right_margin(3)
        self.notes.set_pixels_above_lines(3)
        self.notes.set_pixels_below_lines(3)
        self.notes.set_cursor_visible(True)
        self.notes.get_buffer().connect('changed', self.on_edit_annotation)

        scroll_window = gtk.ScrolledWindow()
        scroll_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_window.add(self.notes)

        frame = gtk.Frame()
        frame.add(scroll_window)

        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)

        self.mark_as_interesting = gtk.ToggleButton()
        self.mark_as_interesting.add(image)
        self.mark_as_interesting.connect('toggled', self.on_mark_as_interesting)

        hbox = gtk.HBox()
        hbox.pack_start(frame)
        hbox.pack_start(self.mark_as_interesting, expand=False)

        return hbox


    def on_hotkey_press(self, widget, event):
        key = gtk.gdk.keyval_name(event.keyval).lower()
        if event.state & gtk.gdk.CONTROL_MASK: key = 'ctrl-' + key
        if event.state & gtk.gdk.SHIFT_MASK: key = 'shift-' + key
    
        hotkeys = {
                'tab': self.cycle_distance_metric,
                'shift-iso_left_tab': self.cycle_score_metric,
                'escape': self.normal_mode,
        }
        
        normal_mode_hotkeys = {
                'j': self.next_group,      'f': self.next_group,
                'k': self.previous_group,  'd': self.previous_group,
                'i': self.insert_mode,      'a': self.insert_mode,
                'z': self.zoom_mode,
                'x': self.pan_mode,
                'c': self.refocus_plot,
                'space': self.toggle_interest,
        }

        if self.get_focus() is not self.notes:
            hotkeys.update(normal_mode_hotkeys)

        if key in hotkeys:
            hotkeys[key]()
            return True

    def on_toggle_filter(self, widget, key):
        if widget.get_active():
            self.filters.add(key)
        else:
            self.filters.discard(key)

        self.update_filter()

    def on_select_groups(self, selection) :
        new_keys = []
        old_keys = self.keys[:]
        self.keys = []
        model, paths = selection.get_selected_rows()

        for path in paths:
            iter = model.get_iter(path)
            key = model.get_value(iter, 0)
            new_keys.append(key)

        # Don't change the order of groups that were already selected.  The 
        # order affects how the color of the group in the score vs rmsd plot, 
        # and things get confusing if it changes.

        for key in old_keys:
            if key in new_keys:
                self.keys.append(key)

        for key in new_keys:
            if key not in self.keys:
                self.keys.append(key)

        # This is an efficiency thing.  The 'J' and 'K' hotkeys works in two 
        # steps: first unselect everything and then select the next row in 
        # order.  Redrawing the plot is expensive, so it's worthwhile to skip 
        # redrawing after that first step.

        if self.keys:
            self.update_plot()
            self.update_annotations()

    def on_select_decoy(self, event):
        self.new_selection = event.ind[0], event.artist.group

    def on_click_plot_mpl(self, event):
        if self.new_selection and event.button == 1:
            index, group = self.new_selection
            path = group.paths[index]
            self.toolbar.set_decoy(os.path.basename(path))

    def on_click_plot_gtk(self, widget, event):
        # Update the selection.

        self.selected_decoy = self.new_selection
        self.new_selection = None
        self.update_plot()

        # Handle a right button press.

        if event.button != 3: return
        if self.toolbar._active == 'PAN': return
        if self.toolbar._active == 'ZOOM': return
        if self.selected_decoy is None: return

        index, group = self.selected_decoy
        path = group.paths[index]
        is_rep = (group.representative == index)

        file_menu = gtk.Menu()

        import yaml

        # The following block is a recipe I copied off the web.  Somehow it 
        # gets YAML to parse the document in order into an OrderedDict.

        mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG
        def dict_representer(dumper, data):
            return dumper.represent_mapping(mapping_tag, data.iteritems())
        def dict_constructor(loader, node):
            return collections.OrderedDict(loader.construct_pairs(node))
        yaml.add_representer(collections.OrderedDict, dict_representer)
        yaml.add_constructor(mapping_tag, dict_constructor)

        with open('pymol_modes.txt') as file:
            pymol_modes = yaml.load(file)

        for key in pymol_modes:
            item = gtk.MenuItem(key)
            item.connect(
                    'activate', self.on_show_decoy_in_pymol,
                    group, index, pymol_modes)
            file_menu.append(item)

        edit_modes = gtk.MenuItem("Edit pymol configuration")
        edit_modes.connect('activate', lambda widget: self.edit_modes())

        copy_path = gtk.MenuItem("Copy path to decoy")
        copy_path.connect('activate', self.on_copy_decoy_path, path)

        if index == group.representative:
            choose_rep = gtk.MenuItem("Reset representative")
            choose_rep.connect(
                'activate', self.on_set_representative, group, None)
        else:
            choose_rep = gtk.MenuItem("Set as representative")
            choose_rep.connect(
                'activate', self.on_set_representative, group, index)

        remove_outlier = gtk.MenuItem("Remove outlier")
        remove_outlier.connect('activate', self.on_remove_outlier, group, index)

        file_menu.append(gtk.SeparatorMenuItem())
        file_menu.append(edit_modes)
        file_menu.append(copy_path)
        file_menu.append(choose_rep)
        file_menu.append(remove_outlier)
        file_menu.foreach(lambda item: item.show())
        file_menu.popup(None, None, None, event.button, event.time)

    def on_show_decoy_in_pymol(self, widget, group, decoy, configs):
        key = widget.get_label()
        open_in_pymol(group, decoy, configs[key])

    def on_copy_decoy_path(self, widget, path):
        import subprocess
        xsel = subprocess.Popen(['xsel', '-pi'], stdin=subprocess.PIPE)
        xsel.communicate(path)

    def on_set_representative(self, widget, group, index):
        group.set_representative(index)
        self.update_plot()

    def on_remove_outlier(self, widget, group, index):
        message = gtk.MessageDialog(
                type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_OK_CANCEL)
        message.set_markup("Remove this outlier?")
        response = message.run()
        message.destroy()

        if response == gtk.RESPONSE_OK:
            group.remove_outlier(index)
            self.update_plot()

    def on_mark_as_interesting(self, widget):
        assert len(self.keys) == 1
        group = self.groups[self.keys[0]]
        interest = widget.get_active()
        group.set_interest(interest)
        self.view.queue_draw()

    def on_edit_annotation(self, buffer):
        assert len(self.keys) == 1
        group = self.groups[self.keys[0]]
        bounds = buffer.get_bounds()
        notes = buffer.get_text(*bounds)
        group.set_notes(notes)

    def on_change_metric(self, widget):
        label = widget.get_label()
        if label in self.score_metrics:
            self.update_score_metric(label)
        if label in self.distance_metrics:
            self.update_distance_metric(label)


    def normal_mode(self):
        self.set_focus(None)

        if self.toolbar._active == 'PAN':
            self.toolbar.pan()

        if self.toolbar._active == 'ZOOM':
            self.toolbar.zoom()

        self.toolbar.unset_decoy()

    def insert_mode(self):
        self.set_focus(self.notes)

    def zoom_mode(self):
        self.toolbar.zoom()

    def pan_mode(self):
        self.toolbar.pan()

    def refocus_plot(self):
        self.toolbar.home()
        self.normal_mode()

    def filter_by(self, filter):
        self.filter = filter
        self.update_filter()

    def next_group(self):
        selection = self.view.get_selection()
        model, paths = selection.get_selected_rows()
        num_paths = model.iter_n_children(None)
        if paths[-1][0] < model.iter_n_children(None) - 1:
            for path in paths: selection.unselect_path(path)
            selection.select_path(paths[-1][0] + 1)
            self.view.scroll_to_cell(paths[-1][0] + 1)

    def previous_group(self):
        selection = self.view.get_selection()
        model, paths = selection.get_selected_rows()
        if paths[0][0] > 0:
            for path in paths: selection.unselect_path(path)
            selection.select_path(paths[0][0] - 1)
            self.view.scroll_to_cell(paths[0][0] - 1)

    def toggle_interest(self):
        current = self.mark_as_interesting.get_active()
        self.mark_as_interesting.set_active(not current)

    def cycle_score_metric(self):
        index = self.score_metrics.index(self.score_metric)
        index = (index + 1) % len(self.score_metrics)
        self.update_score_metric(self.score_metrics[index])

    def cycle_distance_metric(self):
        index = self.distance_metrics.index(self.distance_metric)
        index = (index + 1) % len(self.distance_metrics)
        self.update_distance_metric(self.distance_metrics[index])

    def edit_modes(self):
        import subprocess
        subprocess.call(('gvim', 'pymol_modes.txt'))

    def save_interesting_paths(self):
        chooser = gtk.FileChooserDialog(
                action=gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons=(
                    gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        chooser.set_current_folder(os.getcwd())
        chooser.set_current_name('interesting_paths.txt')

        response = chooser.run()

        if response == gtk.RESPONSE_OK:
            with open(chooser.get_filename(), 'w') as file:
                file.writelines(
                        group.paths[group.representative] + '\n'
                        for group in self.get_interesting_groups())

        chooser.destroy()

    def save_interesting_funnels(self):
        from matplotlib.backends.backend_pdf import PdfPages
        import matplotlib.pyplot as plt

        if not self.get_interesting_groups():
            message = gtk.MessageDialog(
                            type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK)
            message.set_markup("No groups have been marked as interesting.")
            message.run()
            message.destroy()
            return

        chooser = gtk.FileChooserDialog(
                action=gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons=(
                    gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        chooser.set_current_folder(os.getcwd())
        chooser.set_current_name('interesting_funnels.pdf')

        response = chooser.run()

        if response == gtk.RESPONSE_OK:
            pdf = PdfPages(chooser.get_filename())

            for index, group in enumerate(self.get_interesting_groups()):
                plt.figure(figsize=(8.5, 11))
                plt.suptitle(group.directory)

                axes = plt.subplot(3, 2, 1)
                self.plot_score_vs_dist(axes, [group], scores='Total Score', dists='Restraint Dist')

                axes = plt.subplot(3, 2, 2)
                self.plot_score_vs_dist(axes, [group], scores='Total Score', dists='Loop RMSD')

                axes = plt.subplot(3, 2, 3)
                self.plot_score_vs_dist(axes, [group], scores='Dunbrack Score', dists='Restraint Dist')

                axes = plt.subplot(3, 2, 4)
                self.plot_score_vs_dist(axes, [group], scores='Dunbrack Score', dists='Loop RMSD')

                axes = plt.subplot(3, 2, 5)
                self.plot_score_vs_dist(axes, [group], scores='Buried Unsat Score', dists='Restraint Dist')

                axes = plt.subplot(3, 2, 6)
                self.plot_score_vs_dist(axes, [group], scores='Buried Unsat Score', dists='Loop RMSD')

                plt.tight_layout(rect=[0, 0.03, 1, 0.97])
                pdf.savefig(orientation='portrait')
                plt.close()

            pdf.close()

        chooser.destroy()

    def save_interesting_pymol_sessions(self):
        chooser = gtk.FileChooserDialog(
                action=gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons=(
                    gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        chooser.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        chooser.set_current_folder(os.getcwd())

        response = chooser.run()

        if response == gtk.RESPONSE_OK:
            directory = chooser.get_filename()

            with open('pymol_modes.txt') as file:
                base_config = yaml.load(file)['Evaluate decoy in pymol']

            for group in self.get_interesting_groups():
                decoy = group.representative
                config = base_config + '; save ' + os.path.join(
                        directory, group.get_fancy_path('.pse'))

                open_in_pymol(group, decoy, config, gui=False)

        chooser.destroy()

    def save_subangstrom_decoys(self):
        groups = [self.groups[k] for k in self.keys]

        for group in groups:
            job, outputs = os.path.split(group.directory)
            best_decoys = os.path.join(job, 'best_decoys')
            if os.path.exists(best_decoys): shutil.rmtree(best_decoys)
            os.mkdir(best_decoys)

        for group in groups:
            job, outputs = os.path.split(group.directory)
            best_decoys = os.path.join(job, 'best_decoys')

            distances = group.get_distances('Max COOH Distance')
            paths = array(group.paths)[distances < 0.6]

            for path in list(paths):
                id = os.path.basename(path)
                source = os.path.join('..', outputs, id)
                link_name = os.path.join(best_decoys, outputs + '.' + id)
                os.symlink(source, link_name)

    def plot_score_vs_dist(self, axes, groups, **kwargs):
        from graphics import tango
        from itertools import count

        labels = kwargs.get('labels', None)
        xlim = kwargs.get('xlim', self.xlim)
        score_metric = kwargs.get('scores', self.score_metric)
        distance_metric = kwargs.get('dists', self.distance_metric)
        ymin, ymax = inf, -inf

        axes.clear()
        axes.set_xlabel(distance_metric)
        axes.set_ylabel(score_metric)

        if self.selected_decoy is not None:
            sel, selected_group = self.selected_decoy
        else:
            sel, selected_group = None, None
        
        for index, group in enumerate(groups):
            rep = group.representative
            scores = group.get_scores(score_metric)
            distances = group.get_distances(distance_metric)
            ymin = min(ymin, min(scores))
            ymax = max(ymax, 
                    percentile(scores, 85)
                    if score_metric == 'Total Score' else
                    max(scores))
            color = tango.color_from_cycle(index)
            label = labels[index] if labels is not None else ''
            size = clip(7500 / (len(scores)), 2, 15)

            # Highlight the representative decoy.

            axes.scatter(
                    [distances[rep]], [scores[rep]],
                    s=60, c=tango.yellow[1], marker='o', edgecolor='none')

            # Draw the whole score vs distance plot.

            lines = axes.scatter(
                    distances, scores,
                    s=size, c=color, marker='o', edgecolor='none',
                    label=label, picker=True)

            # Highlight the selected decoy, if there is one.

            if group is selected_group:
                axes.scatter(
                        [distances[sel]], [scores[sel]],
                        s=60, c='none', marker='s', edgecolor=tango.yellow[1],
                        linewidth=2)

            lines.paths = group.paths
            lines.group = group

        ypad = 0.05 * (ymax - ymin)
        axes.set_ylim(bottom=ymin-ypad, top=ymax+ypad)
        axes.axvline(1, color='gray', linestyle='--')

        if xlim is None:
            axes.set_xlim(0, 10 if distance_metric == 'Loop RMSD' else 25)
        else:
            axes.set_xlim(0, xlim)

        if labels and 1 < len(groups) < 5:
            axes.legend()


    def update_everything(self):
        self.update_filter()
        self.update_annotations()
        self.update_score_metric(self.score_metric)
        self.update_distance_metric(self.distance_metric)

    def update_score_metric(self, score_metric):
        for widget, id in self.axis_menu_handlers:
            widget.handler_block(id)

        self.axis_menu_items[self.score_metric].set_active(False)
        self.score_metric = score_metric
        self.axis_menu_items[self.score_metric].set_active(True)

        for widget, id in self.axis_menu_handlers:
            widget.handler_unblock(id)

        self.update_plot()

    def update_distance_metric(self, distance_metric):
        for widget, id in self.axis_menu_handlers:
            widget.handler_block(id)

        self.axis_menu_items[self.distance_metric].set_active(False)
        self.distance_metric = distance_metric
        self.axis_menu_items[self.distance_metric].set_active(True)

        for widget, id in self.axis_menu_handlers:
            widget.handler_unblock(id)

        self.update_plot()

    def update_plot(self):
        groups = [self.groups[k] for k in self.keys]
        self.plot_score_vs_dist(self.axes, groups, labels=self.keys)
        self.toolbar.set_decoy("")
        self.canvas.draw()

    def update_annotations(self):
        if len(self.keys) == 1:
            group = self.groups[self.keys[0]]
            self.notes.get_buffer().set_text(group.notes)
            self.notes.set_sensitive(True)
            self.mark_as_interesting.set_active(group.interest)
            self.mark_as_interesting.set_sensitive(True)
        else:
            self.notes.set_sensitive(False)
            self.mark_as_interesting.set_sensitive(False)
        

    def update_filter(self):
        model = self.view.get_model()
        selector = self.view.get_selection()
        model.clear()

        for key in sorted(self.groups):
            group = self.groups[key]
            column = [key]

            if self.filter == 'all':
                model.append(column)

            elif self.filter == 'interesting':
                if group.interest:
                    model.append(column)

            elif self.filter == 'interesting and annotated':
                if group.interest and group.notes:
                    model.append(column)

            elif self.filter == 'interesting and unannotated':
                if group.interest and not group.notes:
                    model.append(column)

            elif self.filter == 'annotated':
                if group.notes:
                    model.append(column)

            elif self.filter == 'uninteresting':
                if not group.interest:
                    model.append(column)

            else:
                model.append(column)

        num_groups = model.iter_n_children(None)
        selector.select_path((0,))


class ModelCanvas (FigureCanvasGTKAgg):

    def __init__(self, figure):
        FigureCanvasGTKAgg.__init__(self, figure)

    def button_press_event(self, widget, event):
        FigureCanvasGTKAgg.button_press_event(self, widget, event)
        return False


class ModelToolbar (NavigationToolbar2GTKAgg):

    toolitems = ( # (fold)
        ('Home', 'Reset original view', 'home', 'home'),
        ('Back', 'Back to previous view', 'back', 'back'),
        ('Forward', 'Forward to next view', 'forward', 'forward'),
        (None, None, None, None),
        ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
        ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
        (None, None, None, None),
        ('Axis', 'Change the distance metric', 'subplots', 'configure_axis'),
        ('Save', 'Save the figure', 'filesave', 'save_figure'),
    )

    def __init__(self, canvas, parent, axis_menu):
        NavigationToolbar2GTKAgg.__init__(self, canvas, parent)
        self.axis_menu = axis_menu
        self.decoy_selected = False

    def configure_axis(self, button):
        self.axis_menu.popup(None, None, None, 0, 0)

    def set_decoy(self, message):
        self.decoy_selected = True
        NavigationToolbar2GTKAgg.set_message(self, message)

    def unset_decoy(self):
        self.decoy_selected = False
        self.set_message("")

    def set_message(self, message):
        if not self.decoy_selected:
            NavigationToolbar2GTKAgg.set_message(self, message)



def load_models(directories, restraints=None, use_cache=True):
    from libraries import pipeline

    groups = collections.OrderedDict()

    for directory in directories:
        if os.path.isdir(directory) and os.listdir(directory):
            if restraints is not None:
                group = ModelGroup(directory, restraints, use_cache)
            else:
                workspace = pipeline.workspace_from_dir(directory)
                pdb_dir = workspace.output_dir
                restraints = workspace.restraints_path
                group = ModelGroup(pdb_dir, restraints, use_cache)

            groups[directory] = group

    return groups

def open_in_pymol(group, decoy, config, gui=True):
    import subprocess

    path = os.path.join(group.directory, group.paths[decoy])
    paths = path, '../data/original_structures/4UN3.pdb.gz'

    wt_name = '4UN3'
    group_name = os.path.basename(path)[:-len('.pdb.gz')]

    #job_target, decoy = os.path.split(path); decoy = decoy[:-len('.pdb.gz')]
    #job, target = os.path.split(job_target)
    #target_path = os.path.join(job, 'inputs', target + '.pdb.gz')
    #wt_path = os.path.join('..', 'structures', 'wt-lig-dimer.pdb')
    #paths = path, wt_path, target_path
    #group_name = group.fancy_path

    #glu_match = re.search('glu_(\d+)', path)
    #glu_position = int(glu_match.group(1)) if glu_match else 38

    #delete_match = re.search('delete_(\d+)', path)
    #num_deletions = int(delete_match.group(1)) if delete_match else 0

    #loop_name = 'delete_{}.glu_{}'.format(num_deletions, glu_position)

    #resfile = os.path.join('..', '05.fixbb_design', loop_name + '.res')
    #loop_file = os.path.join(job, 'loops.dat')

    #with open(loop_file) as file:
    #    fields = file.read().split()
    #    loop_start = int(fields[1])
    #    loop_stop = int(fields[2])
    
    config = config.format(**locals())

    if gui:
        pymol_command = ('pymol', '-qx') + paths + ('-d', config)
    else:
        pymol_command = ('pymol', '-c') + paths + ('-d', config)

    with open(os.devnull, 'w') as devnull:
        subprocess.Popen(pymol_command, stdout=devnull)


if __name__ == '__main__':
    arguments = docopt.docopt(__doc__)
    directories = arguments['<directories>']
    restraints = arguments['--restraints']
    use_cache = not arguments['--force']

    groups = load_models(directories, restraints, use_cache)

    if not arguments['--quiet']:
        gui = ModelView(groups, arguments)
        if not os.fork(): gtk.main()


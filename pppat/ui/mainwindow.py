import os.path

from getpass import getuser
from qtpy.QtWidgets import (QMainWindow, QApplication, QWidget, QPushButton,
                            QHBoxLayout, QVBoxLayout, QAction, qApp, QLabel,
                            QScrollArea, QTextBrowser, QFrame, QTextEdit, QMenu,
                            QFileDialog, QPlainTextEdit, QTableWidgetItem)
from qtpy.QtGui import QIcon, QCursor, QDesktopServices
from qtpy.QtCore import QDir, Slot, Qt, QUrl

from pppat.ui.reminder import EiCReminderWidget
from pppat.ui.console import ConsoleWidget
from pppat.ui.collapsible_toolbox import QCollapsibleToolbox
from pppat.ui.pre_pulse_analysis import PrePulseAnalysisWidget
from pppat.ui.pre_pulse_display import PrePulseDisplayWidget
from pppat.ui.post_pulse_analysis import PostPulseAnalysisWidget
from pppat.ui.log import QPlainTextEditLogger
from pppat.libpulse.pulse_settings import PulseSettings
from pppat.libpulse.utils import wait_cursor
from pppat.libpulse.check_result import CheckResultQTableWidgetItem
from pppat.libpulse.utils_west import is_online, last_pulse_nb
from pppat.ui.BigPicture import BigPicture_disp

from functools import partial  # used to pass parameters for open_url

import pkgutil
from importlib import import_module

from IRFMtb import tsdernier_choc

import logging
logger = logging.getLogger(__name__)

# PPPAT minimum width in pixels
MINIMUM_WIDTH = 800


# Usefull URLs
URLS = {
        'WOI': 'http://www-irfm.intra.cea.fr/Phocea/Page/index.php?id=563',
        'annuaire': 'http://asterope.intra.cea.fr/Phocea/Membres/Annuaire/index.php',
        'FAQ': 'http://maia/EIC/faq',
        'PPPAT GitHub': 'https://github.com/IRFM/PPPAT'
        }

DEFAULT_CONTROL_ROOM_CONFIG = 'configurations/default_EiC.config'
 
class MainWindow(QMainWindow):

    @Slot()
    def display_big_picture(self):
        """
        Display the big picture of the pulse setting.
        """
        # TODO : check data first?
        nominal_scenario = self.pulse_settings.DCS_settings.nominal_scenario
        dp_file = self.pulse_settings.files['dp']
        wfs = self.pulse_settings.waveforms
        pulse_nb = self.pulse_settings.pulse_nb

        BigPicture_disp(nominal_scenario, dp_file, wfs, pulse_nb)    
    
    """
    Central GUI class which also serves as main Controller
    """
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)  # initialize the window
        # Window properties
        self.setWindowTitle('Pre & Post Pulse Analysis Tool for WEST')

        # setup window size to 90% of avail. screen height
        rec = QApplication.desktop().availableGeometry()
        self.resize(MINIMUM_WIDTH, .9*rec.height())

        # Menu Bar
        self.menu_bar()
        
        # Control Room
        # self.control_room = ControlRoom()
        # self.control_room.show()

        # Set the various PPPAT tools as the central Widget
        self.generate_central_widget()
        self.setCentralWidget(self.central_widget)

        # connect the various buttons to their controller
        self.panel_pre_pulse.widget.push_load.clicked.connect(self.load_pulse_settings)
        self.panel_pre_pulse.widget.push_browse.clicked.connect(self.browse_pulse_settings_directory)
        self.panel_pre_pulse.widget.push_check.clicked.connect(self.check_pulse_settings)
        self.panel_pre_pulse.widget.radio_sl.toggled.connect(self.clean_table_pre_test)  # clean table when toggling radio
        self.panel_pre_pulse.widget.radio_shot.toggled.connect(self.clean_table_pre_test)  # clean table when toggling radio
        self.panel_pre_pulse.widget.radio_file.toggled.connect(self.clean_table_pre_test)  # clean table when toggling radio

        # self.panel_pulse_display.widget.push_controlroom.clicked.connect(self.push_control_room)
        self.panel_pulse_display.widget.push_bigpicture.clicked.connect(self.display_big_picture)

        self.panel_post_pulse.widget.edit_pulse_nb.editingFinished.connect(self.get_post_pulse_analysis_nb)
        self.panel_post_pulse.widget.button_check_all.clicked.connect(self.check_post_pulse_all)
        self.panel_post_pulse.widget.radio_last_pulse.clicked.connect(self.get_post_pulse_analysis_nb)
        self.panel_post_pulse.widget.radio_last_pulse.toggled.connect(self.clean_table_post_test)

        # Application icon
        self.setWindowIcon(QIcon('resources/icons/pppat.png'))

        # open some panels at startup
        self.panel_rappels.toggleButton.click()
        self.panel_pre_pulse.toggleButton.click()
        # self.panel_pulse_display.toggleButton.click()
        self.panel_post_pulse.toggleButton.click()
        self.panel_log.toggleButton.click()

        # define set of internal parameters
        self.pulse_settings = None
        self.pulse_settings_dir = None
        self.pulse_settings_files = None
        # the default post pulse is the last pulse
        if is_online():
            self.post_pulse_nb = last_pulse_nb()
        else:
            self.post_pulse_nb = None
        self.panel_post_pulse.widget.pulse_number_label.setText(str(self.post_pulse_nb))

        # look into the post-test directory and get the number of post-tests
        self.post_pulse_tests = self.get_post_pulse_test_list()
        self.post_pulse_nb = 0
        # fill the table with available post tests
        self.fill_post_tests_table()


        # Display user role in the status Bar
        logger.info(f'PPPAT has been launched by user {self.user_login}')
        self.statusBar().showMessage(f'PPPAT launched by {self.user_role}')

        logger.info('Starting PPPAT')

    def menu_bar(self):
        """ Menu bar """
        self.menu = self.menuBar()    
    
        # file menu
        menu_file = self.menu.addMenu('&File')
        action_file_exit = QAction('&Exit', self)
        action_file_exit.setStatusTip('Exit')
        action_file_exit.setShortcut('Ctrl+Q')
        action_file_exit.triggered.connect(qApp.quit)
        menu_file.addAction(action_file_exit)

        # usefull links menu
        menu_links = self.menu.addMenu('Useful &Links')

        action_links_WOI = QAction('&WOI list', parent=self,
                                   statusTip='Open the intranet page with the list of WOIs',
                                   triggered=partial(self.open_url_woi, URLS['WOI']))
        action_links_annuaire = QAction('&Annuaire', parent=self,
                                   statusTip='Open the intranet page with the annuaire',
                                   triggered=partial(self.open_url_woi, URLS['annuaire']))
        action_links_FAQ = QAction('&FAQ des EiC', parent=self,
                                   statusTip='Open the intranet page with the EiC FAQ',
                                   triggered=partial(self.open_url_woi, URLS['FAQ']))
        action_links_github = QAction('&PPPAT GitHub repository', parent=self,
                                   statusTip='Open the official PPPAT github repository',
                                   triggered=partial(self.open_url_woi, URLS['PPPAT GitHub']))
        menu_links.addAction(action_links_WOI)
        menu_links.addAction(action_links_annuaire)
        menu_links.addAction(action_links_FAQ)
        menu_links.addAction(action_links_github)
        
        # Right menu bar (icons)
        # self.menuBar_right = QMenu()
        # self.menuBar_right.triggered.connect(self.toggle_control_room)      
        # self.action_control_room = QAction(icon=QIcon('resources/icons/ui/line-chart-fill_'), 
        #                                   text='Control Room', parent=self)
        # self.action_control_room.setCheckable(True)
        # self.action_control_room.setChecked(False)
        # self.action_control_room.setToolTip('Show/Hide Control Room Window')     
        # JH 2020-12-15 : remove the icon to launch control room from PPPAT directly
        # because the python environement used when launching CR is different from the one expected (??)
        #self.menuBar_right.addAction(self.action_control_room)
        #self.menu.setCornerWidget(self.menuBar_right)

    # def toggle_control_room(self):
    #     """
    #     Show or Hide the Control Room window
    #     """
    #     status = self.action_control_room.isChecked()
    #     if status:
    #         self.control_room.show()
    #     else:
    #         self.control_room.hide()

    def open_url_woi(self, url):
        " Open an URL in an external browser "
        QDesktopServices.openUrl(QUrl(url))

    def generate_central_widget(self):
        """
        Define the central widget, which contain the main GUI of the app,
        mostly the various tools.
        """
        # Define the various collabsible panels (leave "child=" avoid Qt bug)
        self.panel_rappels = QCollapsibleToolbox(child=EiCReminderWidget(), title='Cahier de liaison des EiC / EiC\'s Notebook')
        self.panel_pre_pulse = QCollapsibleToolbox(child=PrePulseAnalysisWidget(), title='Pre-pulse Analysis')
        self.panel_pulse_display = QCollapsibleToolbox(child=PrePulseDisplayWidget(), title='Pre-pulse Display')
        self.panel_post_pulse = QCollapsibleToolbox(child=PostPulseAnalysisWidget(), title='Post-pulse Analysis')
        self.panel_log = QCollapsibleToolbox(child=QPlainTextEditLogger(), title='Logs')
        self.panel_console = QCollapsibleToolbox(child=ConsoleWidget(), title='Python Console')

        # stacking the collapsible panels vertically
        vbox = QVBoxLayout()
        vbox.addWidget(self.panel_rappels)
        vbox.addWidget(self.panel_pre_pulse)
        vbox.addWidget(self.panel_pulse_display)
        vbox.addWidget(self.panel_post_pulse)
        vbox.addWidget(self.panel_log)
        vbox.addWidget(self.panel_console)

        # making the whole panels scrollable
        # The scrollbar should be set for a widget, here a dummy one
        collaps = QWidget()
        collaps.setLayout(vbox)
        scroll = QScrollArea(self)
        scroll.setWidget(collaps)
        scroll.setWidgetResizable(True)
        self.central_widget = scroll

    @property
    def user_login(self):
        """
        User's login name
        """
        return getuser()

    @property
    def user_role(self):
        """
        User's "role", Could be:
            - Engineer in Charge ("eic")
            - Session Leader ("sl")
            - someone else (None)
        Depending of this "role", some options in PPPAT might differ.
        """
        if self.user_login == 'eic' or 'JH218595':
            return 'eic'
        elif self.user_login == 'sl':
            return 'sl'
        else:
            return None

    @Slot()
    def check_pulse_settings(self):
        """ Check pulse setting vs all tests """
        #  disable table sorting before filling the table (otherwise it bugs)
        self.panel_pre_pulse.widget.check_table.setSortingEnabled(False)

        with wait_cursor():
            check_results = self.pulse_settings.check_all(is_online())

        # Fill the check results table with the result property items
        for i, result in enumerate(check_results):
            # The first item in the row is the result name. 
            # I do not use the CheckResultQTableWidgetItem(result, kind='name')
            # otherwise the sorting will be base on the error code, not on the 
            # test name
            self.panel_pre_pulse.widget.check_table.setItem(i, 0, QTableWidgetItem(result.name))
            # other items (result code and result description) 
            # use CheckResultQTableWidgetItem, in order to sort them wrt error
            self.panel_pre_pulse.widget.check_table.setItem(i, 1, CheckResultQTableWidgetItem(result, kind='result'))
            self.panel_pre_pulse.widget.check_table.setItem(i, 2, CheckResultQTableWidgetItem(result, kind='text'))

        # enable table sorting 
        self.panel_pre_pulse.widget.check_table.setSortingEnabled(True)





##            # Check if a watchdog already exists in order not to create a new one for each folder change
##            if not hasattr(self, 'FolderWatcher'):
##                # No pre existing watchdog
##                self.FolderWatcher = ModifFolderWatcher(self.parent,self.LoadFolderName)
##
##            else:
##                # preexisting watchdog: stop and recreate a new one.
##                self.FolderWatcher.resetModifFolderWatcher(self.LoadFolderName)
#
#            # Resets text area and colored squares
#            self.parent.CheckAreaWidget.resetChecks()
#
#            # Update the next shot number
#            self.parent.OnlineSituationAreaWidget.updateNextShot()
#
#            # Update the last modification time
#            self.parent.OnlineSituationAreaWidget.updateModTime()
#

#class ModifFolderWatcher(QtCore.QThread):
#    """
#    Watcher class to monitor file changes on DP.xml or Sup.xml
#    Methods:
#    - modified: actions to perform when a folder/file change is detected
#    - resetFolderWatcher: actions to perform when the user changes the folder to be monitored
#    """
#    def __init__(self,parentWidget,folderName):
#        """
#        Overloaded init to be able to pass the parent widget (for addressing purposes)
#        and the folder to be monitored.
#        """
#        super(ModifFolderWatcher, self).__init__()
#        self.folderName = folderName
#        self.parent = parentWidget
#        # Start the observer process (standard way to do it for the watchdog package)
#        self.observer = Observer()
#        self.event_handler = MyHandler(self.folderName)
#        self.observer.schedule(self.event_handler, self.folderName, recursive=True)
#        self.observer.start()
#        # Method called when a change is detected
#        self.connect(self.event_handler, QtCore.Signal("FolderModified"), self.modified) #PyQt4
#
#
#    def modified(self):
#        """
#        Performs actions when a file change is detected.
#        - Stops the watcher to avoid signal saturation.
#        - Resets the results of checks in the checkArea (returns colored squares to black)
#        - Resets the scenario display area
#        - Update the next shot number
#        - Unload the DCS files to prevent any subsequent check or BigPicture by the user
#        - Remove the changetime from the onlineSituation Area (because the DCS file has to be reloaded
#        """
#        #self.emit(QtCore.SIGNAL("fileModified1"))
#        self.observer.stop()
#        self.parent.CheckAreaWidget.resetScenario()
#        self.parent.scenarioAreaWidget.resetScenarioDisplay()
#        self.parent.OnlineSituationAreaWidget.updateNextShot()
#        self.parent.scenarioAreaWidget.unloadDCS()
#        self.parent.OnlineSituationAreaWidget.removeModTime()
#
#    def resetModifFolderWatcher(self,folderName):
#        """
#        Stops the pre-existing watcher and starts a new one with a new folder to be monitored
#        Similar procedure as in the init.
#        """
#        self.observer.stop()
#        self.folderName = folderName
#        self.observer = Observer()
#        self.event_handler = MyHandler(self.folderName)
#        self.observer.schedule(self.event_handler, self.folderName, recursive=True)
#        self.observer.start()
#        self.connect(self.event_handler, QtCore.Signal("FolderModified"), self.modified)



    @Slot()
    def load_pulse_settings(self):
        """ Load the pulse settings when user clicks on 'load' """
        # clean the pre pulse test result table
        self.clean_table_pre_test()
        # clean the post pulse test result table
        self.clean_table_post_test()

        # construct the pulse settings
        self.pulse_settings = PulseSettings()
        # default loading state
        res_load = False

        with wait_cursor():
            # Load the pulse setting depending on the loading option
            # Load pulse settings from the Session Leader proposal
            if self.panel_pre_pulse.widget.radio_sl.isChecked():
                # TODO : check if SL pulse setting is available
                pulse_settings_SL_avail = True

                if not pulse_settings_SL_avail:
                    logger.error('Pulse settings from SL are not available!')
                else:
                    logger.info('Loading pulse setting from SL')
                    next_pulse = tsdernier_choc() + 1
                    
                    self.panel_pre_pulse.widget.pulse_setting_origin.setText(f'from SL: #{next_pulse}')

                    res_load = self.pulse_settings.load_next_pulse_settings()

            # Load pulse settings from a set of .xml files
            elif self.panel_pre_pulse.widget.radio_file.isChecked():
                if not self.pulse_settings_dir:
                    logger.error('Browse a directory first !')
                else:
                    self.panel_pre_pulse.widget.pulse_setting_origin.setText(
                            self.pulse_settings_dir)
                    logger.info('loading pulse setting from files')

                    res_load = self.pulse_settings.load_from_file(self.pulse_settings_files)

            # Load pulse settings from a pulse number
            elif self.panel_pre_pulse.widget.radio_shot.isChecked():
                pulse_nb = self.panel_pre_pulse.widget.edit_shot.text()

                if is_online():
                    if not pulse_nb:
                        logger.error('Set pulse number first !')
                    else:
                        logger.info(f'loading pulse setting from WEST shot #{pulse_nb}')

                        self.panel_pre_pulse.widget.pulse_setting_origin.setText(
                                f'WEST shot number {pulse_nb}')

                        res_load = self.pulse_settings.load_from_pulse(int(pulse_nb))
                else:
                    logger.error('WEST database not reachable !')

        # if the pulse settings have been correctly loaded
        # some widgets (buttons) are enabled
        # and the nominal scenario trajectory is displayed
        if res_load:
            logger.info('Pulse settings successfully loaded :)')
            self.panel_pre_pulse.widget.push_check.setEnabled(True)
            #self.panel_pulse_display.widget.push_controlroom.setEnabled(True)

            try:
                nominal_trajectory = self.pulse_settings.DCS_settings.nominal_trajectory
                # create a string which summarize the trajectory
                nominal_trajectory_str = ' -> '.join(nominal_trajectory)
                nominal_trajectory_str = nominal_trajectory_str.replace('segment', '')
                logger.info(nominal_trajectory_str)
                self.panel_pre_pulse.widget.pulse_properties.setText(nominal_trajectory_str)

                # get and display the gas valves used in the pulse
                gas_valves = str(self.pulse_settings.fuelling_valves)
                logger.info(f'Gas valve(s) used in the pulse : {gas_valves}')
                self.panel_pre_pulse.widget.pulse_gas_valves.setText(gas_valves)
            except AttributeError as e:
                logger.error(e)
        else:
            logger.error('Problem during pulse settings loading :(')

    @Slot()
    def browse_pulse_settings_directory(self):
        """
        Open a file dialog to select the directory which contains the sup.xml
        and dp.xml files.

        # TODO : also deals with zip or tar.gz file containing the .xml files
        """
        # if user click on the 'browse' button, then automatically select
        # the "file" mode
        self.panel_pre_pulse.widget.radio_file.setChecked(True)
        # open file dialog
        _pulse_settings_dir = \
            QFileDialog.getExistingDirectory(self,
                                             'Select XML/DCS files directory',
                                             directory=QDir.currentPath(),
                                             options=QFileDialog.ShowDirsOnly,  # DontUseNativeDialog
                                             )

        _pulse_settings_files = {
                'sup': f'{_pulse_settings_dir}/Sup.xml',
                'dp': f'{_pulse_settings_dir}/DP.xml'
                }

        # test if both file dp.xml and sup.xml exist. If not -> error msg
        if os.path.isfile(_pulse_settings_files['dp']) and \
            os.path.isfile(_pulse_settings_files['sup']):

            self.pulse_settings_dir = _pulse_settings_dir
            self.pulse_settings_files  = _pulse_settings_files
            logger.info(f'Pulse setting dir set to {self.pulse_settings_dir}')
            logger.info(f'Pulse setting files exist into {self.pulse_settings_dir}')
        else:
            logger.error("One or both of the pulse setting files do not exist!" )

    @Slot()
    def push_control_room(self):
        """
        Display the big picture of the pulse setting.
        """
        # TODO : check data first?
        nominal_scenario = self.pulse_settings.DCS_settings.nominal_scenario
        dp_file = self.pulse_settings.files['dp']
        wfs = self.pulse_settings.waveforms
        pulse_nb = self.pulse_settings.pulse_nb

        BigPicture_disp(nominal_scenario, dp_file, wfs, pulse_nb)
        
        # # TODO: update Control Room shot number?
        # self.control_room.show()

    @Slot()
    def get_post_pulse_analysis_nb(self):
        """
        Update the post pulse number (self.post_pulse_nb)
        from the GUI setup, ie. either the 'last pulse' radio button selected
        or the dedicated QLineEdit
        """
        if self.panel_post_pulse.widget.radio_last_pulse.isChecked():
            # last pulse number
            if is_online():
                self.post_pulse_nb = last_pulse_nb()
            else:
                self.post_pulse_nb = None
        elif self.panel_post_pulse.widget.radio_pulse_nb.isChecked():
            # user defined pulse number
            try:
                self.post_pulse_nb = int(self.panel_post_pulse.widget.edit_pulse_nb.text())
            except ValueError as e:  # no shot number value entered yet
                self.post_pulse_nb = None
        else:
            # this case should not exist !
            logger.error('GUI problem? Cannot read which post pulse to read')

        # Update the QLabel with the post pulse number
        self.panel_post_pulse.widget.pulse_number_label.setText(str(self.post_pulse_nb))
        logger.info(f'Post-Pulse selected: #{self.post_pulse_nb}')


    @Slot()
    def check_post_pulse_all(self):
        """ Check all the (default) post pulse tests """
        # retrieve the post pulse number from the user UI
        self.get_post_pulse_analysis_nb()

        # pulse nb is 0 if not yet set by the user on the GUI
        # pulse nb is -1 if last pulse choosen but user is offline
        # otherwise assume the shot number is correct and perform all the tests
        if not self.post_pulse_nb:
            logger.error('Please first enter a valid shot number!')
        elif self.post_pulse_nb <= 0:
            logger.error('Cannot connect to WEST database. Skipping tests...')
        else:
            # perform all the default post pulse tests
            with wait_cursor():
                logger.info(f'Post-pulse checking... pulse {self.post_pulse_nb}')
                # For all checked tests, perform the tests
                nb_tests = self.panel_post_pulse.widget.check_table.rowCount()
                if nb_tests != len(self.post_pulse_tests):  # just in case ...
                    logger.error(f'The number of available post tests ({len(self.post_pulse_tests)}) does not fit the number of row in the table ({nb_tests}) ?')
                else:
                    for (row, test) in enumerate(self.post_pulse_tests):
                        # assume order of test in the table is the same than order of self.post_pulse_tests
                        status = self.panel_post_pulse.widget.check_table.item(row,0).checkState()
                        if status == Qt.Checked:
                            button_res = self.panel_post_pulse.widget.check_table.cellWidget(row,2)
                            label_res = self.panel_post_pulse.widget.check_table.cellWidget(row,3)
                            self.execute_post_pulse_test(test, button_res, label_res)


    def fill_post_tests_table(self):
        """
        Fill the post test table
        """
        # first update the post pulse number
        self.get_post_pulse_analysis_nb()
        # each row correspond to a specific post-test
        for (row, post_pulse_test) in enumerate(self.post_pulse_tests):
            # add a new row below the last one
            rowPosition = self.panel_post_pulse.widget.check_table.rowCount()
            self.panel_post_pulse.widget.check_table.insertRow(rowPosition)

            # add a checkbox in the row
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)

            if post_pulse_test.default:
                checkbox_item.setCheckState(Qt.Checked)
            else:
                checkbox_item.setCheckState(Qt.Unchecked)

            self.panel_post_pulse.widget.check_table.setItem(rowPosition, 0, checkbox_item)

            # add the launch button in the row
            buttons_test = QPushButton(post_pulse_test.name)
            self.panel_post_pulse.widget.check_table.setCellWidget(rowPosition, 1, buttons_test)

            # add the result button in the row
            buttons_res = QPushButton('  ')
            buttons_res.resize(10, 30)  # all button have same size
            self.panel_post_pulse.widget.check_table.setCellWidget(rowPosition, 2, buttons_res)

            # add the result description in the row
            test_labels = QLabel('')
            self.panel_post_pulse.widget.check_table.setCellWidget(rowPosition, 3, test_labels)

            # connect row's buttons to test methods
            buttons_test.clicked.connect(partial(self.execute_post_pulse_test, post_pulse_test, buttons_res, test_labels))
            buttons_res.clicked.connect(partial(self.plot_post_pulse_test, post_pulse_test))

        # Enable sorting once the table has been filled
        self.panel_post_pulse.widget.check_table.setSortingEnabled(True)
        
    @Slot()
    def clean_table_post_test(self):
        """
        Clean the post test results table (code name, text and button color)
        """
        logger.debug('Changing pulse number: Clean the post pulse table')

        row_nb = self.panel_post_pulse.widget.check_table.rowCount()
        for idx_row in range(row_nb):
            # remove the result code name and text
            self.panel_post_pulse.widget.check_table.cellWidget(idx_row, 2).setText('')
            self.panel_post_pulse.widget.check_table.cellWidget(idx_row, 3).setText('')
            # reset background color
            self.panel_post_pulse.widget.check_table.cellWidget(idx_row, 2).setStyleSheet("")

    def clean_table_pre_test(self):
        """
        Clean the pre pulse test results table
        """
        logger.debug('Cleaning the pre pulse table')
        #  disable table sorting before cleaning the table (otherwise it bugs)
        self.panel_pre_pulse.widget.check_table.setSortingEnabled(False)
        
        row_nb = self.panel_pre_pulse.widget.check_table.rowCount()
        col_nb = self.panel_pre_pulse.widget.check_table.columnCount ()
        # remove the test names and results for all cells
        for idx_row in range(row_nb):
            for idx_col in range(col_nb):
                # clean only if something is allready in the cell
                current_cell = self.panel_pre_pulse.widget.check_table.item(idx_row, idx_col)
                if current_cell:
                    current_cell.setText('')

    @Slot()
    def plot_post_pulse_test(self, post_pulse_test):
        """ plot something meaningfull about a test """
        post_pulse_test.plot(self.post_pulse_nb)

    @Slot()
    def execute_post_pulse_test(self, post_pulse_test, button_res, label_res):
        """
        Execute the test and update the result button and result description
        """
        post_pulse_test.test(self.post_pulse_nb)

        button_res.setText(post_pulse_test.code_name)
        label_res.setText(post_pulse_test.text)

        if post_pulse_test.code == post_pulse_test.OK:
            button_res.setStyleSheet("background-color: green")
        elif post_pulse_test.code == post_pulse_test.WARNING:
            button_res.setStyleSheet("background-color: yellow")
        elif post_pulse_test.code == post_pulse_test.ERROR:
            button_res.setStyleSheet("background-color: red")
        elif post_pulse_test.code == post_pulse_test.UNAVAILABLE:
            button_res.setStyleSheet("background-color: purple")
        elif post_pulse_test.code == post_pulse_test.BROKEN:
            button_res.setStyleSheet("background-color: grey")
        else:
            logger.error(f'Unknow post test result code {post_pulse_test.code}')

    def get_post_pulse_test_list(self):
        """
        Define a list of dictionnaries which describe all available
        post pulse test functions

        """
        post_pulse_tests = []

        # list of the Python file located in the tests post-pulse directory
        check_filenames = [name for _, name, _ in pkgutil.iter_modules(['tests/post_pulse'])]
        check_importers = [imp for imp, _, _ in pkgutil.iter_modules(['tests/post_pulse'])]
        logger.debug(check_filenames)
        logger.debug(check_importers)

        logger.info("########## Looking into post-pulse directory ###########")
        for (importer, file) in zip(check_importers, check_filenames):
            # import the module (here=file)
            i = import_module(importer.path.replace('/', '.') + '.' + file)

            # create a list of all post-pulse Result objects
            # which name starts by 'check_'
            fun_names = dir(i)
            for fun_name in fun_names:
                if 'check_' in fun_name:
                    post_pulse_test = eval(f'i.{fun_name}()')
                    post_pulse_tests.append(post_pulse_test)
#                    except TypeError as e:
#                        logger.error(f'Error in {fun_name}: {e}')

        return post_pulse_tests

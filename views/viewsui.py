import sys
import os
# add the parent directory (absolute, not relative) to the sys.path
# (this makes the games package imports work)
sys.path.append(os.path.abspath(os.pardir))

import cv2
import imutils
from PyQt5 import QtCore, QtWidgets
from PyQt5 import uic, QtGui
from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtGui import QImage, QPixmap, QColor
from PyQt5.QtWidgets import QTableWidgetItem
from games.cv import helpers

# bocce imports
from games.bocce.venue import Venue
from games.bocce.court import Court
from games.bocce.team import Team
from games.bocce.person import Player, Umpire
from games.bocce.throw import Throw
from games.bocce.frame import Frame
from games.bocce.game import Game
from games.camera.camera import USBCamera, RTSPCamera, PubSubImageZMQCamera

import threading



class MovieThread(QThread):
    def __init__(self, camera):
        super().__init__()
        self.camera = camera

    def run(self):
        self.camera.acquire_movie()

class MainWindow(QtWidgets.QMainWindow):
    """
    constructor
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # load the ui file which was made with Qt Creator
        uic.loadUi("views/ui/oddball.ui", self)

        ### config tab ###
        self.tableWidget_cameras.clicked.connect(self.set_camera_source_data)
        self.initialize_tableWidget_cameras_checkedstate()
        self.pushButton_saveTeamNames.clicked.connect(self.save_team_names)

        ### court tab ###
        # each of the cameras are set up in the
        # set_camera_source_data() method
        self.cam1, self.movie_thread_cam1 = None, None
        self.cam2, self.movie_thread_cam2 = None, None
        self.cam3, self.movie_thread_cam3 = None, None
        self.cam4, self.movie_thread_cam4 = None, None
        self.cam5, self.movie_thread_cam5 = None, None
        self.cam6, self.movie_thread_cam6 = None, None
        self.cam8, self.movie_thread_cam7 = None, None
        self.cam8, self.movie_thread_cam8 = None, None

        # movie timer
        #self.movie_thread = None
        self.GAME_MINUTES = 25
        self.gameTimer = QTimer()
        self.time_min_left = 0
        self.time_sec_left = 0
        self.game_time_ui_update()

        # recording
        self.recording = False
        self.pushButton_record.clicked.connect(self.start_movie)

        # camera source radio buttons
        self.radioButton_cam1.clicked.connect(self.get_camera_source)
        self.radioButton_cam2.clicked.connect(self.get_camera_source)
        self.radioButton_cam3.clicked.connect(self.get_camera_source)
        self.radioButton_cam4.clicked.connect(self.get_camera_source)
        self.radioButton_cam5.clicked.connect(self.get_camera_source)
        self.radioButton_cam6.clicked.connect(self.get_camera_source)
        self.radioButton_cam7.clicked.connect(self.get_camera_source)

        # set the no camera image
        self.set_default_img()

        # scoring
        self.g = None
        self.th = None
        self.toggleFrame = 1
        self.pushButton_startGame.clicked.connect(self.start_game)
        self.pushButton_score_frame.clicked.connect(self.score_frame)

    """
    sets the camera view to an oddball image residing on disk
    """
    def set_default_img(self):
        frame = cv2.imread('views/ui/oddball.png')
        frame = imutils.resize(frame, width = 600)
        height, width, channel = frame.shape
        bytesPerLine = 3 * width
        qImg = QImage(frame.data, width, height, bytesPerLine, QImage.Format_RGB888)

        self.label_camera.setPixmap(QPixmap(qImg))
        self.label_camera.repaint()

    """
    sets the camera view source from the radio buttons on the court tab
    @return (camera object, movie thread object)
    """
    def get_camera_source(self):
        # switch case to change the camera source
        if self.radioButton_cam1.isChecked():
            return self.cam1, self.movie_thread_cam1

        elif self.radioButton_cam2.isChecked():
            return self.cam2, self.movie_thread_cam2

        elif self.radioButton_cam3.isChecked():
            return self.cam3, self.movie_thread_cam3

        elif self.radioButton_cam4.isChecked():
            return self.cam4, self.movie_thread_cam4

        elif self.radioButton_cam5.isChecked():
            return self.cam5, self.movie_thread_cam5

        elif self.radioButton_cam6.isChecked():
            return self.cam6, self.movie_thread_cam6

        elif self.radioButton_cam7.isChecked():
            return self.cam7, self.movie_thread_cam7

        elif self.radioButton_cam8.isChecked():
            return self.cam8, self.movie_thread_cam8

        else:
            return None

    """
    this method reads the config tab camera table data
    @return table_data
    """
    def get_tableWidget_cameras_data(self, item):
        rows = self.tableWidget_cameras.rowCount()
        r=0

        table_data = []

        while r < rows:
            table_data.append(
                (
                "cam{}".format(r+1),
                self.tableWidget_cameras.item(r, 0).checkState() == QtCore.Qt.Checked,
                self.tableWidget_cameras.item(r, 1).text(),
                self.tableWidget_cameras.item(r, 2).text(),
                self.tableWidget_cameras.item(r, 3).text()
                )
            )
            r+=1
        #print(table_data)
        return table_data

    """
    this method unchecks all camera sources in the config tab table
    """
    def initialize_tableWidget_cameras_checkedstate(self):
        rows = self.tableWidget_cameras.rowCount()
        r=0
        while r < rows:
            self.tableWidget_cameras.item(r, 0).setCheckState(False)
            r+=1

    """
    this method reads the config tab table and sets up camera sources
    """
    def set_camera_source_data(self):
        table_data = self.get_tableWidget_cameras_data(self.tableWidget_cameras)

        # set Court1 radio button labels
        for t in table_data:
            # if the checkbox in column 1 is checked
            if t[1]:
                #self.radioButton_cam1.setText(t[4])
                getattr(self, "radioButton_{}".format(t[0])).setEnabled(True)
                getattr(self, "radioButton_{}".format(t[0])).setChecked(True)
                getattr(self, "radioButton_{}".format(t[0])).setText(t[4])

                # strip spaces from camera name for video filename purposes
                cam_name = t[4].replace(" ", "")

                # initialize the cameras based on type
                if t[2] == "USBCamera":
                    setattr(self, t[0], USBCamera(name=cam_name,
                        source=int(t[3])))
                elif t[2] == "RTSPCamera":
                    setattr(self, t[0], RTSPCamera(name=cam_name,
                        source=str(t[3])))
                elif t[2] == "PubSubImageZMQCamera":
                    setattr(self, t[0], PubSubImageZMQCamera(name=cam_name,
                        source=str(t[3])))

                # initialize the camera
                getattr(self, t[0]).initialize()

            else:
                getattr(self, "radioButton_{}".format(t[0])).setEnabled(False)

    """
    grabs an image from a camera and displays it
    """
    def get_image_from_cam(self):
        cam = self.get_camera_source()[0]
        frame = cam.get_frame()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channel = frame.shape
        bytesPerLine = 3 * width
        qImg = QImage(frame.data, width, height, bytesPerLine, QImage.Format_RGB888)
        self.label_camera.setPixmap(QPixmap(qImg))
        self.label_camera.repaint()
        return frame

    """
    grabs frames from a camera and displays it continuously
    """
    def update_movie(self):
        frame = cv2.cvtColor(self.get_camera_source()[0].last_frame, cv2.COLOR_BGR2RGB)
        height, width, channel = frame.shape
        bytesPerLine = 3 * width
        qImg = QImage(frame.data, width, height,
            bytesPerLine, QImage.Format_RGB888)
        self.label_camera.setPixmap(QPixmap(qImg))
        self.label_camera.repaint()

    """
    starts movie threads for each active camera and sets the camera source to record
    """
    def start_movie(self):
        if self.recording:
            self.stop_movie()
            return

        table_data = self.get_tableWidget_cameras_data(self.tableWidget_cameras)

        for t in table_data:
            # if the checkbox in column 1 is checked, set it to record
            if t[1]:
                setattr(self, "movie_thread_{}".format(t[0]), MovieThread(getattr(self, t[0])))
                getattr(self, "movie_thread_{}".format(t[0])).start()
                getattr(self, t[0]).start_recording()
                print("started: movie_thread_{}".format(t[0]))

        self.recording = True
        self.update_timer.start(30)

        # cam, movie_thread = self.get_camera_source()
        # movie_thread = MovieThread(cam)
        # movie_thread.start()
        # self.update_timer.start(30)

    """
    stops all movie threads and sets recording to false
    """
    def stop_movie(self):
        table_data = self.get_tableWidget_cameras_data(self.tableWidget_cameras)

        for t in table_data:
            # if the checkbox in column 1 is checked, set it to record
            if t[1]:
                getattr(self, "movie_thread_{}".format(t[0])).quit()
                setattr(self, "movie_thread_{}".format(t[0]), None)
                getattr(self, t[0]).stop_recording()
                print("stopped: movie_thread_{}".format(t[0]))

        self.recording = False

        # movie_thread.quit()
        # time.sleep(.2)

    def set_game_score_palette(self, teamHome, teamAway):
        palette_lcd_teamHome = self.lcdNumber_game_score_teamHome.palette()
        palette_lcd_teamAway = self.lcdNumber_game_score_teamAway.palette()
        pallete_label_teamHome = self.label_game_score_teamHome.palette()
        pallete_label_teamAway = self.label_game_score_teamAway.palette()

        colorA = None
        colorB = None

        if self.g.teamHome.teamBallColor == "purple":
            # purple
            colorA = (226, 43, 138)
        elif self.g.teamHome.teamBallColor == "red":
            # purple
            colorA = (0, 0, 255)

        if self.g.teamAway.teamBallColor == "red":
            # purple
            colorB = (0, 0, 255)
        elif self.g.teamAway.teamBallColor == "purple":
            # purple
            colorB = (226, 43, 138)

        colorA = QColor(colorA[2], colorA[1], colorA[0])
        colorB = QColor(colorB[2], colorB[1], colorB[0])

        palette_lcd_teamHome.setColor(palette_lcd_teamHome.WindowText, colorA)
        palette_lcd_teamAway.setColor(palette_lcd_teamAway.WindowText, colorB)
        pallete_label_teamHome.setColor(pallete_label_teamHome.WindowText, colorA)
        pallete_label_teamAway.setColor(pallete_label_teamAway.WindowText, colorB)

        self.lcdNumber_game_score_teamHome.setPalette(palette_lcd_teamHome)
        self.lcdNumber_game_score_teamAway.setPalette(palette_lcd_teamAway)
        self.label_game_score_teamHome.setPalette(pallete_label_teamHome)
        self.label_game_score_teamAway.setPalette(pallete_label_teamAway)

    def set_status_palette(self, status):

        if status == "game in progress":
            color = (255, 255, 255)
            palette_status = self.label_status.palette()
            color = QColor(color[2], color[1], color[0])
            palette_status.setColor(palette_status.WindowText, color)
            self.label_status.setPalette(palette_status)
        if status.startswith("game winner:"):
            color = None
            if self.g.gameWinner.teamBallColor == "red":
                # red
                color = (0, 0, 255)
            elif self.g.gameWinner.teamBallColor == "purple":
                # purple
                color = (226, 43, 138)
            palette_status = self.label_status.palette()
            color = QColor(color[2], color[1], color[0])
            palette_status.setColor(palette_status.WindowText, color)
            self.label_status.setPalette(palette_status)


    def set_frame_score(self):
        # grab the frame score and update it here
        # todo set team dynamically
        # set the palette

        minhsv = "0,0,15"
        maxhsv = "102,91,255"



        # cam = self.get_camera_source()[0]
        # frame = cam.get_frame()
        frame = cv2.imread("exploratory_code/desk.png")


        cnts, ballMask = helpers.find_ball_contours(frame, minhsv, maxhsv)
        balls = helpers.extract_balls(frame, ballMask, cnts, numBalls=9)
        cluster_idxs = helpers.cluster_balls(balls, clusters=3, debug=False)

        # sort clusters according to length and assume pallino, teamHome, teamAway
        cluster_idxs.sort(key=len)
        print(cluster_idxs)
        pallino_idx = cluster_idxs[0]
        teamHome_idxs = cluster_idxs[1]
        teamAway_idxs = cluster_idxs[2]

        # determine the frame score
        scoreInfo = helpers.calculate_frame_score(frame, balls,
                                                pallino_idx,
                                                teamHome_idxs,
                                                teamAway_idxs, ord("r"))
        frame_annotated, color, frameWinner, framePoints = scoreInfo

        self.tableWidget_frame_score.insertRow(0)
        frameCount=1
        self.tableWidget_frame_score.setItem(0, 0, QTableWidgetItem(str(frameCount)))
        self.tableWidget_frame_score.setItem(0, 1, QTableWidgetItem(str(framePoints)))
        self.tableWidget_frame_score.setItem(0, 2, QTableWidgetItem(frameWinner))
        self.tableWidget_frame_score.item(0, 2).setForeground(QColor(color[2], color[1], color[0]))



        frame = cv2.cvtColor(frame_annotated, cv2.COLOR_BGR2RGB)
        height, width, channel = frame.shape
        bytesPerLine = 3 * width
        qImg = QImage(frame.data, width, height, bytesPerLine, QImage.Format_RGB888)
        self.label_camera.setPixmap(QPixmap(qImg))
        self.label_camera.repaint()

    def save_team_names(self):
        self.teamHome_name = self.textEdit_teamHome.toPlainText()
        self.teamAway_name = self.textEdit_teamAway.toPlainText()

    def initialize_game(self):
        # create a venue
        print("\n[INFO] Creating a venue...")
        v = Venue("Bridge 410")
        print(str(v))

        # create courts
        print("\n[INFO] Creating three courts...")
        cFence = Court("Fence", "north-south")

        # add courts to the venue
        v.add_court(cFence)

        # print the venue string
        print("\n[INFO] Checking to see if the venue has courts...")
        print(str(v) + ": " + v.str_courts())

        # add cameras to the sidewalk court
        print(
            "\n[INFO] Creating a camera and assigning them to a court...")
        cFence.add_birdseye_cam(self.cam8)

        # create some players
        print("\n[INFO] Creating four players...")
        playerA1 = Player(self.textEdit_playerA1.toPlainText(), "null")
        playerA2 = Player(self.textEdit_playerA2.toPlainText(), "null")
        playerB1 = Player(self.textEdit_playerB1.toPlainText(), "null")
        playerB2 = Player(self.textEdit_playerB2.toPlainText(), "null")
        print(str(playerA1))
        print(str(playerA2))
        print(str(playerB1))
        print(str(playerB2))

        # create a team
        print("\n[INFO] Creating two teams and adding players...")
        teamHome = Team(self.teamHome_name)
        teamHome.add_player(playerA1)
        teamHome.add_player(playerA2)
        teamHome.set_team_ball_color("red")
        teamAway = Team(self.teamAway_name)
        teamAway.add_player(playerB1)
        teamAway.add_player(playerB2)
        teamAway.set_team_ball_color("purple")
        print(str(teamHome))
        print(str(teamAway))

        # create a game
        # a game consists of (a) umpire, (b) home team, (c) away team
        print("\n[INFO] Setting up a death match...")
        u = Umpire("Alicia", "null")
        self.g = Game(umpire=u, teamHome=teamAway, teamAway=teamHome)
        print(str(self.g))

        # start the game
        print("\n[INFO] Starting the game...")
        cFence.set_game(self.g)
        print("\n[INFO] Game is being played at {} on {}...".format(
            str(v), str(cFence)))
        self.g.start()
        print("[INFO] Game is started; clock is set...\n")

    def start_game(self):
        # reset score info
        self.tableWidget_frame_score.setRowCount(0)
        self.lcdNumber_frame_score_teamHome.display(str(0))
        self.lcdNumber_frame_score_teamAway.display(str(0))
        self.lcdNumber_game_score_teamHome.display(str(0))
        self.lcdNumber_game_score_teamAway.display(str(0))
        self.label_game_score_teamHome.setText(str("Home"))
        self.label_game_score_teamAway.setText(str("Away"))

        # initialize the game
        self.initialize_game()
        self.g.start()
        status = "game in progress"
        self.label_status.setText(status)
        self.set_status_palette(status)

        # start timer
        self.gameTimer.timeout.connect(self.time_tick)
        self.gameTimer.start(60 * self.GAME_MINUTES)
        self.time_min_left = self.GAME_MINUTES - 1
        self.time_sec_left = 60



    def score_frame(self):
        self.g.play_a_frame()
        self.set_score_temp(self.g.frameWinner, self.g.framePoints)
        winner = self.g.gameWinner
        if winner is not None:
            status = "game winner: {}".format(self.g.gameWinner)
            self.label_status.setText(status)
            self.set_status_palette(status)
            self.set_game_winner_check(winner)
        else:
            self.g.end()

    def set_score_temp(self, frameWinnerTeam, framePoints):
        color = (0, 0, 0)
        # frame score ##################
        if frameWinnerTeam.teamBallColor == "red":
            # red
            color = (0, 0, 255)

        elif frameWinnerTeam.teamBallColor == "purple":
            # purple
            color = (226, 43, 138)

        self.tableWidget_frame_score.insertRow(0)
        self.tableWidget_frame_score.setItem(0, 0, QTableWidgetItem(
            str(self.g.frameCount)))
        self.tableWidget_frame_score.setItem(0, 1, QTableWidgetItem(
            str(framePoints)))
        self.tableWidget_frame_score.setItem(0, 2, QTableWidgetItem(
            str(frameWinnerTeam)))
        self.tableWidget_frame_score.item(0, 2).setForeground(
            QColor(color[2], color[1], color[0]))
        self.set_frame_winner_check(frameWinnerTeam)

        if frameWinnerTeam == self.g.teamHome:
            self.lcdNumber_frame_score_teamHome.display(str(framePoints))
            self.lcdNumber_frame_score_teamAway.display(str(0))
        elif frameWinnerTeam == self.g.teamAway:
            self.lcdNumber_frame_score_teamAway.display(str(framePoints))
            self.lcdNumber_frame_score_teamHome.display(str(0))

        # game score #######################
        self.set_game_score_palette(self.g.teamHome, self.g.teamAway)
        self.label_game_score_teamHome.setText(str(self.g.teamHome))
        self.label_game_score_teamAway.setText(str(self.g.teamAway))
        self.lcdNumber_game_score_teamHome.display(str(self.g.teamHomeScore))
        self.lcdNumber_game_score_teamAway.display(str(self.g.teamAwayScore))

    def set_frame_winner_check(self, frameWinnerTeam):
        check = cv2.imread('views/ui/check_gray.png', cv2.IMREAD_UNCHANGED)
        check = cv2.resize(check, (50, 50))
        height, width, channel = check.shape
        bytesPerLine = 4 * width
        qImg = QImage(check.data, width, height, bytesPerLine, QImage.Format_RGBA8888)

        if frameWinnerTeam == self.g.teamHome:
            self.label_frame_check_home.setPixmap(QPixmap(qImg))
            self.label_frame_check_home.repaint()
            self.label_frame_check_away.clear()
        elif frameWinnerTeam == self.g.teamAway:
            self.label_frame_check_away.setPixmap(QPixmap(qImg))
            self.label_frame_check_away.repaint()
            self.label_frame_check_home.clear()

    def set_game_winner_check(self, gameWinnerTeam):
        check = cv2.imread('views/ui/obie.png', cv2.IMREAD_UNCHANGED)
        check = cv2.resize(check, (50, 50))
        height, width, channel = check.shape
        bytesPerLine = 4 * width
        qImg = QImage(check.data, width, height, bytesPerLine, QImage.Format_RGBA8888)

        if gameWinnerTeam == self.g.teamHome:
            self.label_game_check_home.setPixmap(QPixmap(qImg))
            self.label_game_check_home.repaint()
            self.label_game_check_away.clear()
        elif gameWinnerTeam == self.g.teamAway:
            self.label_game_check_away.setPixmap(QPixmap(qImg))
            self.label_game_check_away.repaint()
            self.label_game_check_home.clear()

    def time_tick(self):
        # subtract a second
        self.time_sec_left -= 1

        # if the seconds < 0, we need to account for minutes
        if self.time_sec_left < 0:
            # subtract a minute
            self.time_min_left -= 1

            # if there are no more minutes
            if self.time_min_left < 0:
                self.time_is_out = True
                self.time_min_left = 0
                self.time_sec_left = 0

            # otherwise, the seconds are set to 59
            else:
                self.time_sec_left = 59

        # update the timer on the UI
        self.game_time_ui_update()

    def game_time_ui_update(self):
        self.lcdNumber_game_time_remaining_min.display(str(self.time_min_left).zfill(2))
        self.lcdNumber_game_time_remaining_sec.display(str(self.time_sec_left).zfill(2))

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec_()
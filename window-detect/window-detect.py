#!/usr/bin/env python

import rospy
import cv2
import numpy as np
import time

from geometry_msgs.msg import Vector3, Point
from mavros_msgs.msg import PositionTarget
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError

# Activate imshow
IMSHOW = True
# Activate video recording
RECORD = False
TESTNUM = 1
# Activate only centralize
ONLY_CENTRALIZE = True


class window_detect:

    def __init__(self):
        self.bridge = CvBridge()
        self.image_sub = rospy.Subscriber('/webcam/image_raw', Image, self.callback)

        self.setpoint_pub_ = rospy.Publisher('mavros/setpoint_raw/local', PositionTarget, queue_size=10)


        # horizontal and forward velocity
        self.velocity_hor = 0.2
        self.velocity_foward = 0.4

        # Error in y and z
        self.dy = 0
        self.dz = 0

        # max error
        self.maxd = 5

        # min window area
        self.minWindowArea = 12000
        
        self.windowDetected = False

        self.drone_pos_ = Point()
    
    def get_bigger_square(self, squares):
        # Recieves a list of squares and returns the bigger one
        bigger_square = None
        bigger_square_area = 0

        for square in squares:
            area = cv2.contourArea(square)
            if area > bigger_square_area:
                bigger_square = square
                bigger_square_area = area

        return bigger_square

    def window_detect(self, cv_image_hsv, cv_image):
 
        # Red mask
        lower_mask = np.array([ 0, 211, 47])
        upper_mask = np.array( [ 179, 255, 75])

        # Generate mask
        mask = cv2.inRange(cv_image_hsv, lower_mask, upper_mask)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=5)
        mask = cv2.dilate(mask, kernel, iterations=9)

        # Find contours
        contours_blk, _ = cv2.findContours(mask.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours_blk = list(contours_blk) 

        # If there is a contour
        if len(contours_blk) > 0:
            # Get the bigger one
            contour = self.get_bigger_square(contours_blk)

            # If the area is bigger than the min area
            if cv2.contourArea(contour) > self.minWindowArea:
                # Get the center of the image
                height, width, _ = cv_image.shape
                centerX, centerY = int(width / 2), int(height / 2)

                # Get the center of the contour
                blackbox = cv2.minAreaRect(contour)
                (x_min, y_min), (w_min, h_min), angle = blackbox

                if IMSHOW:
                # Draw rect
                    temp_image = cv_image.copy()
                    
                    box = cv2.boxPoints(blackbox)
                    box = np.int0(box)
                    cv2.drawContours(temp_image, [box], 0, (0, 0, 255), 10)
                    cv2.circle(temp_image, (int(x_min), int(y_min)), 5, (255, 0, 0), 10)
                    cv2.circle(temp_image, (centerX, centerY), 5, (0, 255, 0), 10)
                    
                    cv2.imshow("temp_img", temp_image)
                    cv2.waitKey(1) & 0xFF

                # Error calculation
                dy = x_min - centerX
                dz = y_min - centerY

                # Error print
                print(f"dy: {dy} | dz: {dz}")

                ## Velocity control
                self.dz = 0
                # if abs(dz) < self.maxd:
                #     self.dz = 0
                # else:
                #     self.dz = 1


                if abs(dy) < self.maxd:
                    self.dy = 0
                else:
                    if dy > 0:
                        self.dy = -1
                    else:
                        self.dy = 1

                # Still centralizing
                if self.dz or self.dy:
                    self.windowDetected = False
                # Centralized
                else:
                    self.windowDetected = True
            
                # Set velocity 

                setpoint_ = PositionTarget()
                vel_setpoint_ = Vector3()

                vel_setpoint_.x = 0
                vel_setpoint_.y = self.velocity_hor * self.dy 
                vel_setpoint_.z = self.velocity_hor * self.dz * (-1)

                yaw_setpoint_ = 0
                # Print velocity
                print(f"x: {vel_setpoint_.x} | y: {vel_setpoint_.y} | z: {vel_setpoint_.z}")

                setpoint_.coordinate_frame = PositionTarget.FRAME_BODY_NED
                
                
                setpoint_.velocity.x = vel_setpoint_.x
                setpoint_.velocity.y = vel_setpoint_.y
                setpoint_.velocity.z = vel_setpoint_.z

                setpoint_.yaw = yaw_setpoint_

                
                self.setpoint_pub_.publish(setpoint_)
               
            
            # If any contour is bigger than the min area
            # stay put
            else:
                setpoint_ = PositionTarget()
                vel_setpoint_ = Vector3()

                vel_setpoint_.x = 0
                vel_setpoint_.y = 0
                vel_setpoint_.z = 0
                yaw_setpoint_ = 0
                setpoint_.coordinate_frame = PositionTarget.FRAME_BODY_NED
                
                setpoint_.velocity.x = vel_setpoint_.x
                setpoint_.velocity.y = vel_setpoint_.y
                setpoint_.velocity.z = vel_setpoint_.z

                setpoint_.yaw = yaw_setpoint_

                # self.setpoint_pub_.publish(setpoint_)
    
    def move(self, cv_image):
        # Move foward
        setpoint_ = PositionTarget()
        vel_setpoint_ = Vector3()

        vel_setpoint_.x = self.velocity_foward
        vel_setpoint_.y = 0
        vel_setpoint_.z = 0
        yaw_setpoint_ = 0
        setpoint_.coordinate_frame = PositionTarget.FRAME_BODY_NED
        
        setpoint_.velocity.x = vel_setpoint_.x
        setpoint_.velocity.y = vel_setpoint_.y
        setpoint_.velocity.z = vel_setpoint_.z

        setpoint_.yaw = yaw_setpoint_

        self.setpoint_pub_.publish(setpoint_)

        if IMSHOW:
            cv2.imshow("img", cv_image)
            cv2.waitKey(1) & 0xFF
    
    def callback(self, data):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(data, "bgr8")
        except CvBridgeError as e:
            print(e)

        cv_image_hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        # self.window_detect(cv_image_hsv, cv_image)
        if not self.windowDetected:
            print("Detecting window")
            self.window_detect(cv_image_hsv, cv_image)
        else:
            print("Moving")
            self.move(cv_image)



def main():
    rospy.init_node('window_detect', anonymous=True)
    wd = window_detect()
    time.sleep(3)
    try:
        rospy.spin()
    except KeyboardInterrupt:
        print("Shutting down")
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()

#include <stdio.h>
#include "opencv2/opencv.hpp"
#include <vector>

using namespace std;
using namespace cv;

//#define VIDEO_DEBUG
#define SENTINEL_ENABLE

/*
#define MIN_ROSS_FRAMES 45
#define MAX_ROSS_FRAMES 70
#define FRAME_DIVISOR 1
*/
#define FRAME_DIVISOR 3
#define MIN_ROSS_FRAMES (30 / FRAME_DIVISOR)
#define MAX_ROSS_FRAMES (900 / FRAME_DIVISOR)

// Frame positioning constants
#define MSG_REGION_START_X 0.14
#define MSG_REGION_START_Y 0.4
#define MSG_REGION_END_X 0.85
#define MSG_REGION_END_Y 0.65

void fastMultiMatch(const Mat& img, const Mat& templ, vector<Point>& results, double thresh) {
    // perform template matching
    Mat res = Mat::zeros(img.size() + Size(1,1) - templ.size(), CV_32FC1);

    matchTemplate(img, templ, res, CV_TM_CCORR_NORMED);
    threshold(res, res, 0.9, 1, CV_THRESH_TOZERO);

    Point minloc, maxloc;
    double minval, maxval;
    while(true) {
        minMaxLoc(res, &minval, &maxval, &minloc, &maxloc);

        if(maxval >= thresh) {
            // extract best values
            results.push_back(maxloc);
            floodFill(res, maxloc, Scalar(0), 0, Scalar(.1), Scalar(1.));
        } else {
            break;
        }
    }
}

int main(int argc, char **argv) {
    if(argc != 2) {
        // takes video file as argument
        return -1;
    }

    // open video capture device
    VideoCapture input(argv[1]);
    if(!input.isOpened())
        return -1;

    // read the template file
    Mat rossTemplate = imread("bobross.png", 1);
    int rossWidth = rossTemplate.cols,
        rossHeight = rossTemplate.rows;

#ifdef VIDEO_DEBUG
    // iterate through frames
    namedWindow("image");

    moveWindow("image", 1940, 10);
#endif
#ifdef SENTINEL_ENABLE
    printf("[sentinel] system starting\n");
    fflush(stdout);
#endif

    Mat msg, health, frame;
    int seen_frames = 0;

    unsigned long processed = 0;
    double time = 0;
    unsigned long int lastTicks = getTickCount();
    unsigned long int lastDrawTicks = getTickCount();
    unsigned int updateMod = 10;
    int deaths = 0;
    while(input.read(frame)) { // process frames 
        processed++;
        time += (getTickCount()-lastTicks)/getTickFrequency();
        lastTicks = getTickCount();
        if(processed % FRAME_DIVISOR != 0) continue;

        Size imsize = frame.size();

        // figure out crop boundaries
        int msg_starty = imsize.height * MSG_REGION_START_Y,
            msg_endy = imsize.height * MSG_REGION_END_Y;

        // extract important regions
        msg = frame(Rect(
                    imsize.width    * MSG_REGION_START_X,
                    imsize.height   * MSG_REGION_START_Y,
                    imsize.width    * (MSG_REGION_END_X - MSG_REGION_START_X),
                    imsize.height   * (MSG_REGION_END_Y - MSG_REGION_START_Y)));

        vector<Point> pts;
        fastMultiMatch(msg, rossTemplate, pts, 0.1);

#ifdef VIDEO_DEBUG
        for(Point p : pts) {
            rectangle(msg, p, Point(p.x + rossTemplate.cols,
                        p.y + rossTemplate.rows), Scalar(0,255,0), 1);
            p.y -= 2;
            putText(msg, "BOB ROSS", p, FONT_HERSHEY_SIMPLEX, 0.5, Scalar(0,255,0));
        }
#endif

        int finish = 0;
        if(pts.size() == 2) {
            // identify left and right points
            Point left, right;
            if(pts[0].x < pts[1].x) {
                left = pts[0];
                right = pts[1];
            } else {
                left = pts[1];
                right = pts[0];
            }
            Point lcenter = Point(left.x + (rossWidth/2), left.y + (rossHeight/2)),
                  rcenter = Point(right.x + (rossWidth/2), right.y + (rossHeight/2));

            // make sure the Rosses are aligned by comparing their X and Y distances 
            if((rcenter-lcenter).y < 8) {
                seen_frames++;
#ifdef VIDEO_DEBUG
                circle(msg, lcenter, 8, Scalar(0,255,0));
                circle(msg, rcenter, 8, Scalar(0,0,255));
                line(msg, lcenter, rcenter, Scalar(0,255,255));

                double ird = norm(lcenter - rcenter);
                char buf[64];
                snprintf(buf, 64, "IRD: %.3lf SF: %d", ird, seen_frames);
                putText(msg, buf, Point(0, msg.rows-4), FONT_HERSHEY_SIMPLEX, 0.5, Scalar(0,255,0));
#endif
            } else {
                finish = 1;
            }
        } else {
            finish = 1;
        }

        if(finish == 1) {
            if(seen_frames > MIN_ROSS_FRAMES && seen_frames < MAX_ROSS_FRAMES) {
                seen_frames = -999999999;
                printf("[sentinel] died\n");
                fflush(stdout);
            } else {
                seen_frames = 0;
            }
        }

#ifdef VIDEO_DEBUG
        if((processed % updateMod == 0) || (seen_frames > 0)) {
            unsigned int drawTicks = getTickCount();
            double timeSinceLastDraw = (drawTicks - lastDrawTicks)/getTickFrequency();
            lastDrawTicks = drawTicks;

            if(timeSinceLastDraw == 0)
                timeSinceLastDraw = 1;

            if(seen_frames <= 0) {
                double delta = abs(timeSinceLastDraw - 1);
                if(delta > 2) {
                    updateMod = (unsigned int)(processed/time);
                } else if(delta > 0.2) {
                    if(timeSinceLastDraw > 1)
                        updateMod--;
                    else
                        updateMod++;
                }
            }

            char buf[64];
            snprintf(buf, 64, "#%lu %.2f FPS %u ur t~%.2f",
                    processed, processed/time, updateMod, processed/30.0/60);
            putText(msg, buf, Point(60,msg.rows-4), FONT_HERSHEY_PLAIN, 1, Scalar(0,255,0));
            imshow("image", msg);

            int rc = waitKey(1);
            if(rc >= 0 && rc != 65513) {
                break;
            }
        }
#endif
#ifdef SENTINEL_ENABLE
        if(processed % 30 == 0) {
            printf("[sentinel] run fps=%.2f\n", (processed / time));
            fflush(stdout);
        }
#endif
    }

#ifdef SENTINEL_ENABLE
    printf("[sentinel] stream ended\n");
    fflush(stdout);
#endif

    return 0;
}

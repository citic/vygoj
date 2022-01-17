import { Request, Response } from 'express';
import Course from '../models/course.js';
import database from '../util/database.js';
import git from '../util/git.js';
import errorController from './errorController.js';

/**
 * Controls the Courses homepage.
 *
 * The course page lists the enrolled and available courses for students, and
 * the owned courses for professors. If professors want to enroll a course,
 * they must register an account as students.
 */
class CourseController {
  // Get the homepage view
  // eslint-disable-next-line class-methods-use-this
  getIndex(req: Request, res: Response) {
    // Show the homepage
    res.render('courses/courses', {
      stylesheet: 'courses',
      title: 'Vygotsky Online Judge (Vygoj)',
      user: req.session.user,
      breadcumbs: [
      ],
      // The list of user's courses
      myCourses: Course.fetchMyCourses(),
      // The list of available courses for this user
      availableCourses: Course.fetchAllCourses(),
    });
  }

  // Get a page where professors admin their courses
  // eslint-disable-next-line class-methods-use-this
  getAdminCourse(req: Request, res: Response) {
    // Show the homepage
    res.render('courses/admin', {
      stylesheet: 'courses',
      title: 'Admin my courses - Vygoj',
      user: req.session.user,
      breadcumbs: [
        { href: '/course/admin', text: 'Admin my courses' },
      ],
    });
  }

  // Professor added/changed a repository or enabled/disabled a course
  // eslint-disable-next-line class-methods-use-this
  async postAdminCourse(req: Request, res: Response) {
    // Get the action
    const action = req.body.action as string;
    const repoUrl = req.body.new_repo_url as string;
    if (action === 'add_repo' && req.session.user) {
      try {
        // TODO: log this event
        console.log(`Cloning ${repoUrl}...`);
        await git.gitClient.clone(repoUrl);
        // The clone was successful, add this repo to the user inthe database
        database.users().updateOne({ _id: req.session.user._id }, {
          $addToSet: {
            repositories: {
              url: repoUrl,
              courses: [],
            },
          },
        });
      } catch (error) {
        console.error(error);
      }
    }
    // Show the same page again
    res.redirect('/course/admin');
  }

  // Get the contents page for a course
  // eslint-disable-next-line class-methods-use-this
  getCourse(req: Request, res: Response) {
    const courseId = req.params.courseId as string;
    const course = Course.findById(courseId);
    if (course) {
      res.render('courses/course', {
        stylesheet: 'courses',
        title: `${course.title} - Vygoj`,
        user: req.session.user,
        breadcumbs: [
          { href: `/course/${course.id}`, text: course.code },
        ],
        course,
      });
    } else {
      errorController.getNotFound(req, res);
    }
  }
} // class

// Export the singleton controller
const courseController = new CourseController();
export default courseController;

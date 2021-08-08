import { Request, Response } from 'express';
import Course from '../models/course.js';
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
    res.render('courses', {
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

  // Get the contents page for a course
  // eslint-disable-next-line class-methods-use-this
  getCourse(req: Request, res: Response) {
    const courseId = req.params.courseId as string;
    const course = Course.findById(courseId);
    if (course) {
      res.render('course', {
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

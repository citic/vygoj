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
  getIndex(req: Request, res: Response) {
    // Show the homepage
    res.xhtml().render('courses', {
      stylesheet: 'courses',
      title: 'Vygotsky Online Judge (Vygoj)',
      user: {
        id: 'login',
        name: 'User',
      },
      breadcumbs: [
      ],
      // The list of user's courses
      myCourses: Course.fetchMyCourses(),
      // The list of available courses for this user
      availableCourses: Course.fetchAllCourses(),
    });
  }

  // Get the contents page for a course
  getCourse(req: Request, res: Response) {
    const courseId = req.params.courseId;
    const course = Course.findById(courseId);
    if (course) {
      res.render('course', {
        stylesheet: 'courses',
        title: `${course.title} - Vygoj`,
        user: {
          id: 'login',
          name: 'User',
        },
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

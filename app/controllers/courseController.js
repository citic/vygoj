import Course from '../models/course.js';

/**
 * Controls the Courses homepage.
 *
 * The course page lists the enrolled and available courses for students, and
 * the owned courses for professors. If professors want to enroll a course,
 * they must register an account as students.
 */
class CourseController {
  // Get the homepage view
  getIndex(req, res) {
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
  getCourse(req, res) {
    const courseId = req.params.courseId;
    const course = Course.findById(courseId);
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
      course: course,
    });
  }
} // class

// Export the singleton controller
const courseController = new CourseController();
export default courseController;

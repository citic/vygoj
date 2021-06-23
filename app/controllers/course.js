/**
 * Controls the Courses homepage.
 *
 * The course page lists the enrolled and available courses for students, and
 * the owned courses for professors. If professors want to enroll a course,
 * they must register an account as students.
 *
 * A course has four states:
 *
 * - Editing: When it is being created by professors
 * - Active: When it is being used by students
 * - Finalized: When its finish date passed or professors closed it.
 * - Future: When it is ready but its start date is comming.
 */
class CourseController {
  // Get the homepage view
  static getIndex(req, res) {
    res.xhtml().render('index', {
      title: 'Vygoj: Vygotsky Online Judge',
    });
  }
} // class

// Export the singleton controller
const courseController = new CourseController();
export default courseController;

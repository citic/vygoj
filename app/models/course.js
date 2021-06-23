/**
 * A course is an educative event lasting -but not limited to- an academic term
 * where professors and students share and build knowledge and skills. In a
 * systems perspective, a course is compound of several resources:
 *
 * - Attributes: name, title, description, image, startDate, finishDate
 * - Instructors (teachers, professors)
 * - Students
 * - Sections that can be nested
 * - Pages that contain grading assignments, such as
 *   - Questions
 *   - Programming problems
 * - Grades
 *
 * A course has four states:
 *
 * - Editing: When it is being created by professors
 * - Active: When it is being used by students
 * - Finalized: When its finish date passed or professors closed it.
 * - Future: When it is ready but its start date is comming.
 */
export default class Course {
  // todo: filter params: state
  static fetchAllCourses() {
    // todo: this test will be replaced by a database query
    return [
      {
        id: 'c17',
        code: 'CI0117',
        title: 'Programación paralela y concurrente',
        image: '/img/logo2.svg',
        instructors: [
          { id: 'u13', name: 'Jeisson Hidalgo-Céspedes' },
        ],
        statistics: {
          students: 21,
          sections: 356, // lessons?
          problems: 64,
          questions: 128,
        },
      },
      {
        id: 'c08',
        code: 'CI0113',
        title: 'Programación II',
        image: '/img/logo2.svg',
        instructors: [
          { id: 'u8', name: 'Edgar Casasola-Murillo' },
        ],
        statistics: {
          students: 23,
          sections: 123,
          problems: 27,
          questions: 94,
        },
      },
    ];
  }
}

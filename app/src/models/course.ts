import { ObjectId } from 'mongodb';

// Simulates the course database. It will be replaced by a real DB/files access
const allCourses = [
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
    contents: [
    ],
  },
  {
    id: 'c1',
    code: 'CI0112',
    title: 'Programación I en C',
    image: '/img/logo2.svg',
    instructors: [
      { id: 'u13', name: 'Jeisson Hidalgo-Céspedes' },
    ],
    statistics: {
      students: 18,
      sections: 148, // lessons?
      problems: 39,
      questions: 19,
    },
    repo: 'progra1-21b',
    contents: [
      {
        name: 'IO',
        title: 'Input/output',
        folder: '1.1_intro_io',
        contents: [
          {
            name: 'lost_in_space_ints',
            title: 'Enteros perdidos en el espacio',
            folder: 'lost_in_space_ints',
          },
          {
            name: 'enclosing_lines',
            title: 'Encerrar las líneas',
            folder: 'enclosing_lines',
          },
        ],
      },
      {
        name: 'expr_cond',
        title: 'Expresiones y condicionales',
        folder: '1.2_expressions_if',
        contents: [
          {
            name: 'line_numbers',
            title: 'Números de línea',
            folder: 'line_numbers',
          },
          {
            name: 'hours_mins_secs',
            title: 'Normalizar horas, minutos, segundos',
            folder: 'hours_mins_secs',
          },
        ],
      },
    ],
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
    contents: [
    ],
  },
  {
    id: 'stdthr',
    code: 'CI0117a',
    title: 'Hilos estándar en C/C++',
    image: '/img/logo2.svg',
    repo: '',
    instructors: [
      { id: 'u13', name: 'Jeisson Hidalgo-Céspedes' },
    ],
    statistics: {
      students: 20,
      sections: 2,
      problems: 7,
      questions: 0,
    },
    contents: [ {
      name: 'cstdthr',
      title: 'Hilos estándar en C',
      type: 'folder',
      folder: 'problem',
      contents: [ {
        name: 'intro_vygoj',
        title: 'Introducción al juez en línea',
        type: 'problem',
        folder: 'intro_vygoj',
      }, {
        name: 'c_hello_std',
        title: 'Hola mundo estándar en C',
        type: 'problem',
        folder: 'c_hello_std',
      }, {
        name: 'c_thrd_sleep',
        title: 'Hilos durmientes en C',
        type: 'problem',
        folder: 'c_thrd_sleep',
      }, {
        name: 'c_thrd_mtx',
        title: 'Exclusión mutua en C',
        type: 'problem',
        folder: 'c_thrd_mtx',
      /* }, {
        name: 'c_local_storage',
        title: 'Local storage en C',
        type: 'problem',
        folder: 'c_local_storage', */
      }, {
        name: 'c_prime_counter',
        title: 'Contador de primos en C',
        type: 'problem',
        folder: 'c_prime_counter',
      }, ],
    }, /* {
      name: 'cppstdthr',
      title: 'Hilos estándar en C++',
      type: 'folder',
      contents: [ {
        name: 'c_hello_std',
        title: 'Hola mundo estándar en C++',
        type: 'problem',
        folder: 'c_hello_std',
      }, {
        name: 'c_thrd_sleep',
        title: 'Hilos durmientes en C++',
        type: 'problem',
        folder: 'c_thrd_sleep',
      }, {
        name: 'c_thrd_mtx',
        title: 'Exclusión mutua en C++',
        type: 'problem',
        folder: 'c_thrd_mtx',
      }, {
        name: 'c_local_storage',
        title: 'Local storage en C++',
        type: 'problem',
        folder: 'c_local_storage',
      }, ],
    }, */ ],
  },
];

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
  _id: ObjectId | undefined;

  // todo: filter params: state
  static fetchMyCourses() {
    // todo: this test will be replaced by a database query
    return [Course.findById('stdthr')];
  }

  static fetchAllCourses() {
    // todo: this test will be replaced by a database query
    // return [Course.findById('c1'), Course.findById('c08')];
    return [];
  }

  static findById(id: string) {
    return allCourses.find((course) => course.id === id);
  }
}

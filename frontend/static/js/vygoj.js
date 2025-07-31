/// Class to create enum objects serializable to JSON
class Enum {
  constructor(fields) {
    const instance = {
      // Each field will be a property of the Enum class
      ...fields,

      // Serialize this enum value to a JSON object
      toJSON: function() {
        return Object.keys(this).reduce((jsonObject, key) => {
          // Only copy string properties to the JSON object, skip methods
          if (typeof this[key] === 'string') {
            jsonObject[key] = this[key];
          }
          return jsonObject;
        }, {}); // Provide an initial empty object as reduction target
      }, // toJSON

      // Load this enum value from a JSON object
      parse: function(jsonObject) {
        if (Object.values(this).includes(jsonObject)) {
          return jsonObject;
        }
        throw new Error(`Invalid enum value: ${jsonObject}`);
      }
    };

    // Make properties of enum object inmutable
    return Object.freeze(instance);
  }
}

// Execution status for a test case or entire submission
export const Status = new Enum({
  PENDING: 'pending',
  PASSED: 'passed',
  WRONG: 'wrong',
  TIMEOUT: 'timeout',
  COMPILER_ERROR: 'compilerError',
  RUNTIME_ERROR: 'runtimeError',
  INTERNAL_ERROR: 'internalError',
});

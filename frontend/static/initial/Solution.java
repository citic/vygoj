import java.util.Scanner;

/**
 * TODO(you): Purpose of your solution.
 */
public class Solution {
  /**
   * Parse formatted data from standard input.
   */
  private Scanner input = null;

  /**
   * Default constructor.
   */
  public Solution() {
  }

  /**
   * Start the execution of the solution.
   *
   * @param args Command line arguments
   * @throws Exception if an unhandled error occurs while running the solution
   */
  public static void main(final String[] args) throws Exception {
    final Solution solution = new Solution();
    solution.start();
  }

  /**
   * Start the solution.
   * Set up standard input, and clean it when solution finishes.
   *
   * @throws Exception if an unhandled error occurs while running the solution
   */
  public void start() throws Exception {
    assert this.input == null;
    try {
      // Create object to read data from standard input
      this.input = new Scanner(System.in);
      // Run problem solution
      this.run();
    } finally {
      // Close the scanner of standard input
      this.input.close();
    }
  }

  /**
   * Run the solution. This procedure is called from start().
   *
   * @throws Exception if an unhandled error occurs while running the solution
   */
  public void run() throws Exception {
    // TODO: Solve the problem applying good programming practices.
  }
}

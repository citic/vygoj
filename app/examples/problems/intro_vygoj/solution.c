#include <float.h>
#include <stdio.h>

int main(void) {
  double value = 0.0, max = -DBL_MAX;
  size_t count = 0;
  while (scanf("%lg", &value) == 1) {
    if (value > max) {
      max = value;
    }
    ++count;
  }
  if (count > 0) {
    printf("%lg\n", max);
  }
}

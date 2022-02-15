#include <stdio.h>

int main(void) {
  printf("Hello from main thread\n");
  int count = 0;
  scanf("%d", &count);
  for (int index = 0; index < count; ++index) {
    printf("Hello from secondary thread %d\n", index);
  }
}

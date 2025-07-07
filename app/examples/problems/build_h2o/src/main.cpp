// Copyright 2025 ECCI-UCR CC-BY 4.0
#include <barrier>
#include <cassert>
#include <iostream>
#include <mutex>
#include <semaphore>
#include <thread>
#include <vector>

std::counting_semaphore hydrogen_multiplex(2);
std::counting_semaphore oxygen_multiplex(1);
std::barrier device_barrier(3);  // Synchronization point for 2H and 1O
size_t molecule_count = 0;  // Number of molecules formed

void bond(const char atom);
void hydrogen();
void oxygen();

int main() {
  // Create threads that represent atoms according to values in stdin
  char atom_type{};
  std::vector<std::thread> threads;
  while (std::cin >> atom_type) {
    switch (atom_type) {
      case 'H': threads.emplace_back(std::thread(hydrogen)); break;
      case 'O': threads.emplace_back(std::thread(oxygen)); break;
      default: assert(false); break;
    }
  }
  // Wait for all atoms to finish
  for (std::thread& thread : threads) {
    thread.join();
  }
  // Report number of molecules formed
  std::cout << "Molecules formed: " << molecule_count << std::endl;
  return 0;
}

void hydrogen() {
  hydrogen_multiplex.acquire();
  device_barrier.arrive_and_wait();
  bond('H');
  device_barrier.arrive_and_wait();
  hydrogen_multiplex.release();
}

void oxygen() {
  oxygen_multiplex.acquire();
  device_barrier.arrive_and_wait();
  bond('O');
  device_barrier.arrive_and_wait();
  oxygen_multiplex.release();
}

// Do not modify this procedure:
void bond(const char atom) {
  // Check two hydrogen and one oxygen atoms are in the device to form water
  static size_t hydrogen_count = 0, oxygen_count = 0;
  static std::mutex mutex;
  mutex.lock();
  switch (atom) {
    case 'H': ++hydrogen_count; break;
    case 'O': ++oxygen_count; break;
    default: assert(false); break;
  }
  if (hydrogen_count == 2 && oxygen_count == 1) {
    ++molecule_count;
    hydrogen_count = oxygen_count = 0;  // Reset counts for next molecule
    mutex.unlock();
    // Here the code to control the device will be added in the future
    // device.induce();
  } else {
    mutex.unlock();
  }
}

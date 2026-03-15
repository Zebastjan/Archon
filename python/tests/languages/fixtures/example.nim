## Example Nim file for integration testing

import os, strutils

type
  Person = object
    name: string
    age: int

  Employee = object of Person
    id: int
    salary: float

## Greet a person by name
proc greet(p: Person): string =
  result = "Hello, " & p.name

## Calculate annual salary
proc calculateAnnualSalary(e: Employee): float =
  result = e.salary * 12.0

## Generic identity function
proc identity[T](x: T): T =
  result = x

## Main program entry point
proc main() {.async.} =
  let person = Person(name: "Alice", age: 30)
  let greeting = greet(person)
  echo greeting

when isMainModule:
  main()

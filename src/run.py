# Imports
from pyfiglet import Figlet
from book import Book
import streamlit as st
import json


# Get the OpenAI API key from the config file
def get_api_key():
    # Read the config file
    with open('config.json', 'r') as f:
        # Return the OpenAI key
        return json.load(f)['OpenAI_key']

# Draw the given text in a figlet
def draw(text):
    # Create a new figlet object
    f = Figlet()

    # Print the figlet
    print(f.renderText(text))


# Get a selection from a list of options
def get_option(options):
    # Print the available options
    print('Please select an option:')
    for i, option in enumerate(options):
        print(f'[{i + 1}] {option}')

    # While the user input is not valid
    while True:
        try:

            # Get the selection
            selection = int(input('> '))

            # Check if the selection is valid
            if selection < 1 or selection > len(options):
                raise ValueError

            # Return the selection
            return selection

        # User input was not valid
        except ValueError:
            print('Invalid option. Please try again.')


# Main function
def main():
    # Draw the title
    draw('BookGPT')

    # Check if the user wants to generate a new book or not
    if get_option(['Generate a book', 'Exit']) - 1:
        return

    # Get the number of chapters
    #print('How many chapters should the book have?')
    chapters = 5
    #chapters = int(input('> '))
    #if chapters <= 1:
     #   words = 1

    # Get the number of words per chapter
    #print('How many words should each chapter have?')
    words = 1200
    # Check if it is below 1200
    #words = int(input('> '))
    #if words >= 2000:
      #  words = 2000
       # print('The number of words per chapter has been set to 1000. (The max number of words per chapter)')

    # Get the category of the book
    #print('What is the category of the book?')
    #category = input('> ')
    category = 'Science Fiction'

    # Get the topic of the book
    #print('What is the topic of the book?')
    #topic = input('> ')
    topic = """William a 27-year-old boy moves to an unfamiliar city and rents a house, where he will begin a new life. He is quiet, socially awkward, and dislikes interacting with people, Nevertheless, he will inevitably encounter various situations requiring social interaction in the future, as well as many moments where friends will be needed, whether for problem-solving or emotional support. Despite his quirky personality, this also makes it easier for him to find genuine friends. These friends, while tolerating his rationality and sharpness, care about him and try their best to help him resolve the problems he encounters. His life is simple. He lives frugally, spending only the necessary money on essential daily necessities. When it comes to interpersonal relationships, he highly values "choice" and "necessity." He believes that no friend or person has any obligation to do anything for him, and he himself has no justification to demand that anyone must do anything for him. If someone tells the protagonist, "You are very important to me," he would feel flustered and overwhelmed. He takes commitments seriously and will always do his utmost to fulfill promises he has made. However, he is usually cautious and tends to avoid making promises altogether. 未自华为备意录"""
    # What is the tolerance of the book?
    #print('What is the tolerance of the book? (0.8 means that 80% of the words will be written 100%)')
    tolerance = 0.6
    #tolerance = float(input('> '))
    #if tolerance <= 0 or tolerance >= 0.9:
     #   tolerance = 0.8

    # Do you want to add any additional parameters?
    #print('Do you want to add any additional parameters?')
    #if get_option(['No', 'Yes']) - 1:
        #print(
         #   'Please enter the additional parameters in the following format: "parameter1=value1, parameter2=value2, ..."')
        #additional_parameters = input('> ')
        #additional_parameters = additional_parameters.split(', ')
        #for i in range(len(additional_parameters)):
            #additional_parameters[i] = additional_parameters[i].split('=')
        #additional_parameters = dict(additional_parameters)
    #else:
    #additional_parameters = {}

    # Initialize the Book
    book = Book(chapters=chapters, words_per_chapter=words, topic=topic, category=category, tolerance=tolerance)
               # **additional_parameters)

    # Print the title"Eruption: The Science of Volcanoes"
    print(f'Title: {book.get_title()}')

    # Ask if he wants to change the title until he is satisfied
    while True:
        print('Do you want to generate a new title?')
        if get_option(['No', 'Yes']) - 1:
            print(f'Title: {book.get_title()}')
        else:
            break

    # Print the structure of the book
    print('Structure of the book:')
    structure = book.get_structure()
    structure = book.get_structure()
    print(structure)

    # Ask if he wants to change the structure until he is satisfied
    while True:
        print('Do you want to generate a new structure?')
        if get_option(['No', 'Yes']) - 1:
            print('Structure of the book:')
            structure = book.get_structure()
            print(structure)
        else:
            break

    print('Generating book...')

    # Initialize the book generation
    book.finish_base()
    # Generate the book
    book.get_content()
    # Save the book
    book.save_book()
    print('Book saved.')

# Run the main function
if __name__ == "__main__":
    main()

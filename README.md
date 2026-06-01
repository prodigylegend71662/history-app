# His-Story

#### Video Demo: [(https://www.youtube.com/watch?v=OTfAAD2uXfI)]

#### Description:

His Story of History is a web-based application created as my CS50 final project. The goal of this project is to reimagine how people learn history by transforming historical events into a social media-style feed. Instead of reading traditional textbooks or static timelines, users can scroll through a dynamic feed where each “post” represents an important historical event. This approach makes learning history more interactive, engaging, and easier to follow.

The inspiration for this project came from the way people consume information on modern social media platforms. Most users are familiar with scrolling through posts, timestamps, and structured content in apps like social feeds. I wanted to apply that same familiar experience to education, specifically history, so that learning feels more natural and less abstract.

The application is built using Flask as the backend framework, along with HTML, CSS, and JavaScript for the frontend. Flask is responsible for routing, rendering pages, and handling server-side logic. HTML is used to structure the pages, CSS is used to style the interface and create a clean feed layout, and JavaScript is used to add interactivity and dynamic behavior to the application.

The project is organized into several key components. The main file, `app.py`, contains the Flask application and defines all routes used in the system. This includes rendering the home page, loading the feed, and managing any backend logic required for displaying content. The `templates/` folder contains all HTML files, including the main feed interface where historical events are displayed in a structured format. These templates are rendered by Flask and allow dynamic content to be inserted into the pages. The `static/` folder contains CSS and JavaScript files that control the styling and interactivity of the application.

Each historical event is displayed as a feed-style post. These posts include a title, timestamp, and content section. Some posts also include additional UI elements such as progress indicators or read-only message formats, depending on how the historical event is presented. The structure is designed to mimic a modern social media feed, where each entry is clearly separated and easy to read.

One of the main design decisions in this project was to present history in a format that users are already familiar with. By using a feed-based structure, the learning curve is reduced and users can immediately understand how to navigate the content. Another design choice was to keep the interface minimal and clean so that the focus remains on the historical information rather than unnecessary visual complexity.

The project also includes voice functionality, which allows historical content to be read aloud to the user. This feature improves accessibility and provides an alternative way of engaging with the material. It also makes the application more immersive, as users can both read and listen to historical events at the same time. This was implemented using browser-based speech capabilities.

In addition to the voice feature, the application structure is designed to be extendable. New historical events can be added easily to the feed, and the system can be expanded with additional features such as filtering by time period, marking events as read, or categorizing history into different eras.

Throughout the development of this project, I learned how to design a full-stack web application using Flask and how to structure a frontend that is both functional and visually clear. I also improved my understanding of combining backend logic with frontend design to create a smooth user experience.

Overall, His-Story is a project that aims to make history more engaging by combining educational content with modern interface design. By turning historical events into a scrollable feed, the application creates a more intuitive and interactive way to explore the past.

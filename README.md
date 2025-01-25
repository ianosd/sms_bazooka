# Web App to send SMS

This is a web app where you can upload a csv file and send an sms based on each row in the file.
Each row is supposed to have a phone number column and possibly additional data columns, which can be 
filled into a template.

The app uses the API of smslink.ro for sending sms messages. In truth, all the funcionality provided by the app
is also covered by smslink.ro, under the feature https://www.smslink.ro/sms/marketing/send-sms-template.php.
The code here may be useful if extended to allow for different messaging systems.

# The frontent

### First

Install deps from project root `yarn` or `npm i`

### Start development server with:

`yarn start:dev` or `npm run start:dev`

It's possible to use a different port by specifying this first like so: 

`CVA_PORT=7788 yarn start:dev` to start with port 7788. Same for npm just include `CVA_PORT=7788` at the beginning.

### Build for production

`yarn build` or `npm run build`

## Deploy

To deploy, copy the files under public/bundle to your favorite public folder

# The backend
The backend is a `bottle`-based server that uses the API of smslink.ro to send sms messages.
It also maintains a record of the messaging history, which can be querried.

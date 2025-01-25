const HtmlWebpackPlugin = require('html-webpack-plugin');
const path = require('path');
var webpack = require('webpack');
require("dotenv").config();

process.env.NODE_ENV = process.env.NODE_ENV || 'development'
process.env.CVA_PORT = process.env.CVA_PORT || 9000

const config = function (mode) {
    let conf = {
        mode: mode,
        entry: ['./src/index.js'],
        module: {
            rules: [
            {
                test: /\.js$/,
                exclude: /(node_modules|bower_components)/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['@babel/preset-env'],
                        plugins: [['@babel/plugin-transform-runtime', {"regenerator": true}]]
                    }
                }
            },
            {
                test: /\.html$/,
                exclude: /(node_modules|bower_components)/,
                use: {
                    loader: 'html-loader',
                    options: {}
                }
            },
            {
              test: /\.css$/,
              use: ['style-loader', 'css-loader'],
            },
        ]
        },
        output: {
            path: path.resolve(__dirname, 'public/bundle/'),
            filename: 'bundle.js',
            publicPath: '/',
        },
        plugins: [new HtmlWebpackPlugin({template: "src/index.ejs"})],
        devServer: {
            watchOptions: {
                ignored: /node_modules/
            },
            contentBase: 'public',
            compress: true,
            hot: true,
            port: process.env.CVA_PORT
        }
    }

    if (mode === 'development') {
        conf.plugins.push(new webpack.HotModuleReplacementPlugin())
        conf.plugins.push(new webpack.NoEmitOnErrorsPlugin())
    }
    conf.plugins.push(new webpack.DefinePlugin({"process.env.API_ENDPOINT": JSON.stringify(process.env.API_ENDPOINT)}))

    return conf
}

module.exports = config(process.env.NODE_ENV)